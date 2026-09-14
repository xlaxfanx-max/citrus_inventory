"""A small star schema for analysis, separate from the operational tables.

The operational schema (lots, sampling, forecast) is normalized for fast,
safe inserts. The accuracy, readiness and scorecard questions are analytic:
"how many days after its pack-by date did each lot actually pack, by plant
and month?" Answering them from the operational tables means walking
Lot -> Prediction -> PackPlan -> PlanRecommendation -> PlanDecision each time.

These tables are deliberately denormalized: dimension rows carry the
context you slice by (plant, grower, variety, calendar), fact rows carry
one measurable event each (a prediction, a packout, a management decision)
with foreign keys into the dimensions. They are rebuilt in full by
`manage.py build_warehouse` (extract, transform, load) and never written by
the application, so they can be granted read-only to analysts and pointed
at from DBeaver or a notebook without touching production rows.

Date keys are integers in yyyymmdd form so a calendar dimension can be
joined on an int and grouped by its year, month and week columns.
"""

from django.db import models


def date_key(day):
    """yyyymmdd integer for a date, or None."""
    return None if day is None else day.year * 10000 + day.month * 100 + day.day


class DimDate(models.Model):
    date_key = models.IntegerField(primary_key=True)
    date = models.DateField(unique=True)
    year = models.SmallIntegerField()
    quarter = models.SmallIntegerField()
    month = models.SmallIntegerField()
    week_of_year = models.SmallIntegerField()
    day_of_week = models.SmallIntegerField(help_text='ISO: Monday is 1.')
    is_monday = models.BooleanField()

    class Meta:
        db_table = 'dw_dim_date'
        ordering = ['date_key']

    def __str__(self):
        return self.date.isoformat()


class DimPlant(models.Model):
    plant_key = models.BigIntegerField(primary_key=True, help_text='lots_plant.id')
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    weekly_pack_capacity_bins = models.DecimalField(max_digits=9, decimal_places=1, null=True)

    class Meta:
        db_table = 'dw_dim_plant'

    def __str__(self):
        return self.code


class DimLot(models.Model):
    """One row per lot with its grower and plant context flattened in."""

    lot_key = models.BigIntegerField(primary_key=True, help_text='lots_lot.id')
    plant = models.ForeignKey(DimPlant, on_delete=models.PROTECT, related_name='lots')
    lot_no = models.CharField(max_length=30)
    grower_no = models.CharField(max_length=20)
    grower_name = models.CharField(max_length=100)
    block = models.CharField(max_length=50, blank=True)
    variety = models.CharField(max_length=10)
    receiving_color = models.CharField(max_length=2)
    intake_cci_mean = models.FloatField(null=True)
    receive_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+')
    harvest_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+', null=True)
    bins_received = models.IntegerField(null=True)
    status = models.CharField(max_length=12)
    packed_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+', null=True)
    days_in_storage = models.IntegerField()

    class Meta:
        db_table = 'dw_dim_lot'

    def __str__(self):
        return f'{self.plant.code} {self.lot_no}'


class FactPrediction(models.Model):
    """One row per nightly forecast (the model's claim on a given day)."""

    lot = models.ForeignKey(DimLot, on_delete=models.CASCADE, related_name='predictions')
    as_of_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+')
    pack_by_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+', null=True)
    days_to_pack_by = models.IntegerField(null=True)
    hold_until_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+', null=True)
    hold_days_remaining = models.IntegerField(null=True)
    deadline_kind = models.CharField(max_length=8, blank=True)
    cci_now = models.FloatField()
    stage = models.CharField(max_length=2)
    drift_per_day = models.FloatField()
    decay_rate = models.FloatField()
    decay_flag = models.BooleanField()
    confidence = models.CharField(max_length=4)
    n_points = models.SmallIntegerField()
    method = models.CharField(max_length=40, blank=True)
    model_version = models.CharField(max_length=40)

    class Meta:
        db_table = 'dw_fact_prediction'
        constraints = [models.UniqueConstraint(fields=['lot', 'as_of_date'], name='dw_one_prediction_per_lot_day')]


class FactPackout(models.Model):
    """One row per packout run: what the lot actually did."""

    lot = models.ForeignKey(DimLot, on_delete=models.CASCADE, related_name='packouts')
    packed_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+')
    cartons_fancy = models.IntegerField()
    cartons_choice = models.IntegerField()
    cartons_standard = models.IntegerField()
    cartons_products = models.IntegerField()
    cartons_total = models.IntegerField()
    fresh_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    bins_packed = models.DecimalField(max_digits=9, decimal_places=1, null=True)
    is_final = models.BooleanField()
    packout_color = models.CharField(max_length=2, blank=True)
    decay_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    meets_spec = models.BooleanField(null=True)
    days_in_storage = models.IntegerField()
    forecast_pack_by_date = models.ForeignKey(
        DimDate, on_delete=models.PROTECT, related_name='+', null=True,
        help_text='Pack-by date of the latest forecast made on or before the pack date.',
    )
    days_after_pack_by = models.IntegerField(null=True, help_text='Positive means packed late against the forecast.')

    class Meta:
        db_table = 'dw_fact_packout'
        constraints = [models.UniqueConstraint(fields=['lot', 'packed_date'], name='dw_one_packout_per_lot_day')]


class FactDecision(models.Model):
    """One row per management decision against a published recommendation."""

    lot = models.ForeignKey(DimLot, on_delete=models.CASCADE, related_name='decisions')
    plan_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+')
    decided_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+')
    plan_version = models.IntegerField()
    rank = models.IntegerField()
    action = models.CharField(max_length=16)
    recommended_pack_by_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+', null=True)
    status = models.CharField(max_length=10)
    reason = models.CharField(max_length=20, blank=True)
    planned_pack_date = models.ForeignKey(DimDate, on_delete=models.PROTECT, related_name='+', null=True)
    market_regime = models.CharField(max_length=12, blank=True)
    after_lock = models.BooleanField()
    decided_by = models.CharField(max_length=150, blank=True)
    source_decision_id = models.BigIntegerField(unique=True, help_text='forecast_plandecision.id')

    class Meta:
        db_table = 'dw_fact_decision'
