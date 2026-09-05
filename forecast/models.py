"""One Prediction row per lot per as_of_date, written by the drift model in
forecast/model.py (via `manage.py build_predictions`, nightly and after
every scored photo). Every row carries model_version and the exact inputs
used so it can be audited and re-run.

PackPlan, PlanRecommendation and PlanDecision are the versioned plan and
management-decision record required by the pilot protocol: what the system
recommended, when, on what numbers, and what the GM did about it.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import OuterRef, Subquery
from django.urls import reverse
from django.utils import timezone

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


class PlanAction(models.TextChoices):
    """The next action the ranked plan asks for on a lot. Codes are stable;
    lots.planning decides which one applies and in what order."""

    DECAY_RISK = 'decay_risk', 'Decay risk'
    PACK_OVERDUE = 'pack_overdue', 'Pack overdue'
    PACK_THIS_WEEK = 'pack_this_week', 'Pack this week'
    RETAKE_PHOTO = 'retake_photo', 'Retake photo'
    SAMPLE_DUE = 'sample_due', 'Sample due'
    PACK_SOON = 'pack_soon', 'Pack soon'
    SCORING = 'scoring', 'Scoring'
    NEEDS_BASELINE = 'needs_baseline', 'Needs baseline'
    MONITOR = 'monitor', 'Monitor'


class PackPlan(models.Model):
    """A versioned snapshot of the ranked packing plan for one plant.

    Published by the Monday report, from the board, or by `publish_plan`.
    Every recommendation in it is frozen with the prediction it came from, so
    a management decision can be tied to exactly what the system said at the
    time and later compared with the lot's real outcome. Plans are never
    edited; a new version is published instead.
    """

    class Source(models.TextChoices):
        REPORT = 'report', 'Monday report'
        BOARD = 'board', 'Published from the board'
        COMMAND = 'command', 'Management command'

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='pack_plans')
    plan_date = models.DateField()
    version = models.PositiveIntegerField(help_text='Increments per plant with every publish.')
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.BOARD)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='published_plans'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    model_version = models.CharField(max_length=40)
    settings_snapshot = models.JSONField(default=dict, blank=True)
    locked_at = models.DateTimeField(
        null=True, blank=True, help_text='When the GM locked the week schedule against this plan.'
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_plans'
    )

    class Meta:
        ordering = ['-plan_date', '-version']
        constraints = [models.UniqueConstraint(fields=['plant', 'version'], name='one_plan_version_per_plant')]
        indexes = [models.Index(fields=['plant', 'plan_date'])]

    def __str__(self):
        return f'{self.plant.code} plan v{self.version} ({self.plan_date})'

    @property
    def is_locked(self):
        return self.locked_at is not None

    def get_absolute_url(self):
        return reverse('forecast:plan_detail', args=[self.pk])


class PlanRecommendation(models.Model):
    """One lot's line in a PackPlan: the action, the numbers it rested on,
    and (through `decisions`) what management did with it."""

    plan = models.ForeignKey(PackPlan, on_delete=models.CASCADE, related_name='recommendations')
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='plan_recommendations')
    prediction = models.ForeignKey(
        Prediction, on_delete=models.SET_NULL, null=True, blank=True, related_name='plan_recommendations'
    )
    rank = models.PositiveIntegerField()
    action = models.CharField(max_length=16, choices=PlanAction.choices)
    requires_decision = models.BooleanField(
        default=False, help_text='True for pack-now and decay actions; management must record a decision.'
    )
    pack_by_date = models.DateField(null=True, blank=True)
    stage = models.CharField(max_length=2, choices=Color.choices, blank=True)
    cci_now = models.FloatField(null=True, blank=True)
    confidence = models.CharField(max_length=4, choices=Prediction.Confidence.choices, blank=True)
    decay_flag = models.BooleanField(default=False)
    bins_remaining = models.DecimalField(max_digits=9, decimal_places=1, null=True, blank=True)
    room_name = models.CharField(max_length=50, blank=True)
    days_in_storage = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['plan', 'rank']
        constraints = [models.UniqueConstraint(fields=['plan', 'lot'], name='one_recommendation_per_plan_lot')]

    def __str__(self):
        return f'{self.plan}: #{self.rank} {self.lot.lot_no} {self.get_action_display()}'

    @property
    def latest_decision(self):
        """Current decision: the most recent one recorded (decisions are add-only)."""
        return next(iter(self.decisions.all()), None)

    def outcome(self, today):
        """What actually happened to the lot after this recommendation."""
        lot = self.lot
        if lot.status == Lot.Status.PACKED and lot.packed_date:
            delta = (lot.packed_date - self.pack_by_date).days if self.pack_by_date else None
            return {'status': 'packed', 'date': lot.packed_date, 'days_after_pack_by': delta, 'days_abs': abs(delta) if delta is not None else None}
        if lot.status == Lot.Status.DUMPED:
            return {'status': 'dumped', 'date': None, 'days_after_pack_by': None, 'days_abs': None}
        overdue = self.pack_by_date is not None and today > self.pack_by_date
        late = (today - self.pack_by_date).days if overdue else None
        return {'status': 'in_storage', 'date': None, 'days_after_pack_by': late, 'days_abs': late}


class PlanDecision(models.Model):
    """Management's response to one recommendation. Add-only: a change of mind
    is a new row, and the newest row is the current decision."""

    class Status(models.TextChoices):
        ACCEPTED = 'accepted', 'Accepted'
        DEFERRED = 'deferred', 'Deferred'
        OVERRIDDEN = 'overridden', 'Overridden'

    class Reason(models.TextChoices):
        CUSTOMER_ORDER = 'customer_order', 'Customer order or ship date'
        SIZE_GRADE = 'size_grade', 'Size, grade or label demand'
        CAPACITY = 'capacity', 'Line capacity or labor'
        CHANGEOVER = 'changeover', 'Changeover cost or run minimum'
        QUALITY_DISAGREE = 'quality_disagree', 'Disagree with the model color or quality call'
        FRUIT_NOT_READY = 'fruit_not_ready', 'Holding for color or maturity'
        LOGISTICS = 'logistics', 'Room access or logistics'
        DATA_ISSUE = 'data_issue', 'Data issue (quantity, sample or import)'
        OTHER = 'other', 'Other (explain in notes)'

    recommendation = models.ForeignKey(PlanRecommendation, on_delete=models.CASCADE, related_name='decisions')
    status = models.CharField(max_length=10, choices=Status.choices)
    reason = models.CharField(max_length=20, choices=Reason.choices, blank=True)
    planned_pack_date = models.DateField(
        null=True, blank=True, help_text='When management intends to pack instead (required when deferring).'
    )
    notes = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='plan_decisions'
    )
    decided_at = models.DateTimeField(default=timezone.now)
    after_lock = models.BooleanField(default=False, help_text='Recorded after the plan was locked.')

    class Meta:
        ordering = ['-decided_at', '-id']

    def __str__(self):
        return f'{self.recommendation.lot.lot_no}: {self.get_status_display()}'

    @property
    def needs_reason(self):
        return self.status in (self.Status.DEFERRED, self.Status.OVERRIDDEN)

    @property
    def reason_complete(self):
        """Scorecard rule: a deferral or override counts only with a structured reason."""
        if not self.needs_reason:
            return True
        if not self.reason:
            return False
        return bool(self.notes.strip()) if self.reason == self.Reason.OTHER else True

    def clean(self):
        errors = {}
        if self.needs_reason and not self.reason:
            errors['reason'] = 'A structured reason is required when deferring or overriding.'
        if self.status == self.Status.DEFERRED and not self.planned_pack_date:
            errors['planned_pack_date'] = 'Say when the lot will be packed instead.'
        if self.reason == self.Reason.OTHER and not self.notes.strip():
            errors['notes'] = 'Explain the reason in the notes.'
        if self.status == self.Status.ACCEPTED and self.planned_pack_date and self.recommendation_id:
            rec = self.recommendation
            if rec.pack_by_date and self.planned_pack_date > rec.pack_by_date:
                errors['planned_pack_date'] = 'A planned date after the pack-by date is a deferral, not an acceptance.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        plan = self.recommendation.plan
        self.after_lock = bool(plan.locked_at and self.decided_at > plan.locked_at)
        super().save(*args, **kwargs)
