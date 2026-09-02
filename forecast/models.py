"""One Prediction row per lot per as_of_date, written by the drift model in
forecast/model.py (via `manage.py build_predictions`, nightly and after
every scored photo). Every row carries model_version and the exact inputs
used so it can be audited and re-run.
"""

from django.db import models
from django.db.models import OuterRef, Subquery

from lots.models import Color, Lot, Plant


class PredictionQuerySet(models.QuerySet):
    def latest_per_lot(self, on_or_before=None):
        """At most one row per lot: its most recent prediction, optionally
        restricted to as_of_date <= on_or_before (a date, or an OuterRef such
        as OuterRef('lot__packed_date') to use a per-lot date).

        Use as a Prefetch queryset so the board and validation screens load
        one row per lot instead of the lot's whole nightly history."""
        candidates = Prediction.objects.filter(lot=OuterRef('lot'))
        if on_or_before is not None:
            candidates = candidates.filter(as_of_date__lte=on_or_before)
        newest = candidates.order_by('-as_of_date', '-id').values('pk')[:1]
        return self.filter(pk=Subquery(newest))


class Prediction(models.Model):
    class Confidence(models.TextChoices):
        LOW = 'low', 'Low'
        MED = 'med', 'Medium'
        HIGH = 'high', 'High'

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='predictions')
    as_of_date = models.DateField()
    cci_now = models.FloatField()
    stage = models.CharField(max_length=2, choices=Color.choices)
    drift_per_day = models.FloatField()
    predicted_yellow_date = models.DateField(null=True, blank=True)
    pack_by_date = models.DateField(null=True, blank=True)
    decay_rate = models.FloatField(default=0.0, help_text='Fraction, 0-1, over the last two samples.')
    decay_flag = models.BooleanField(default=False)
    confidence = models.CharField(max_length=4, choices=Confidence.choices, default=Confidence.LOW)
    model_version = models.CharField(max_length=40)
    inputs = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PredictionQuerySet.as_manager()

    class Meta:
        ordering = ['-as_of_date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['lot', 'as_of_date'], name='one_prediction_per_lot_day')
        ]
        indexes = [models.Index(fields=['lot', 'as_of_date'])]

    def __str__(self):
        return f'{self.lot} as of {self.as_of_date}: pack by {self.pack_by_date}'

    @property
    def n_points(self):
        return len(self.inputs.get('points', []))

    def days_to_pack_by(self, today):
        return (self.pack_by_date - today).days if self.pack_by_date else None

    @property
    def decay_pct(self):
        return round(self.decay_rate * 100, 1)


class ReportDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='report_deliveries')
    report_date = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    recipients = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=250, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-report_date', 'plant__code']
        constraints = [
            models.UniqueConstraint(
                fields=['plant', 'report_date'], name='one_report_delivery_per_plant_date'
            )
        ]

    def __str__(self):
        return f'{self.plant.code} report {self.report_date} ({self.status})'
