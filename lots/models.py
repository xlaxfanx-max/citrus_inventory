"""Core inventory: plants, rooms, growers, lots, room moves, packouts,
import batches, user-to-plant assignment and the model settings table.

Data model follows docs/v1-build-spec.md. Lots are never deleted; a lot
leaves the board by changing status to packed or dumped.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, validate_email
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Color(models.TextChoices):
    """Lemon storage color progression, in order. Fruit only moves forward."""

    DARK_GREEN = 'DG', 'Dark green'
    LIGHT_GREEN = 'LG', 'Light green'
    SILVER = 'S', 'Silver'
    YELLOW = 'Y', 'Yellow'


COLOR_RANK = {Color.DARK_GREEN: 0, Color.LIGHT_GREEN: 1, Color.SILVER: 2, Color.YELLOW: 3}


class Plant(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True, help_text='Famous plant code, e.g. SLA1.')
    city = models.CharField(max_length=100, blank=True)
    report_recipients = models.TextField(
        blank=True,
        help_text='Comma-separated email addresses that receive this plant\'s Monday report.',
    )
    weekly_pack_capacity_bins = models.DecimalField(
        max_digits=9,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Planning capacity in bins per week. Leave blank when not yet known.',
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'

    def clean(self):
        invalid = []
        for email in self.recipient_list:
            try:
                validate_email(email)
            except ValidationError:
                invalid.append(email)
        if invalid:
            raise ValidationError({
                'report_recipients': f'Invalid email address(es): {", ".join(invalid)}'
            })

    @property
    def recipient_list(self):
        return [e.strip() for e in self.report_recipients.replace(';', ',').split(',') if e.strip()]


class Room(models.Model):
    class RoomType(models.TextChoices):
        STORAGE = 'storage', 'Storage'
        DEGREENING = 'degreening', 'Degreening'

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=50)
    room_type = models.CharField(max_length=12, choices=RoomType.choices, default=RoomType.STORAGE)
    target_temp_f = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        ordering = ['plant__code', 'name']
        constraints = [models.UniqueConstraint(fields=['plant', 'name'], name='unique_room_per_plant')]

    def __str__(self):
        return self.name


class Grower(models.Model):
    name = models.CharField(max_length=100)
    sunkist_grower_no = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ['sunkist_grower_no']

    def __str__(self):
        return f'{self.sunkist_grower_no} {self.name}'.strip()


class LotQuerySet(models.QuerySet):
    def in_storage(self):
        return self.filter(status=Lot.Status.IN_STORAGE)

    def at_plant(self, plant):
        return self.filter(plant=plant) if plant is not None else self

    def delete(self):
        raise ValidationError('Lots are never deleted. Set status to packed or dumped instead.')

    def hard_delete(self):
        """Explicit escape hatch for the local demo reset command only."""
        return super().delete()


class Lot(models.Model):
    class Status(models.TextChoices):
        IN_STORAGE = 'in_storage', 'In storage'
        PACKED = 'packed', 'Packed'
        DUMPED = 'dumped', 'Dumped'

    class Variety(models.TextChoices):
        EUREKA = 'Eureka', 'Eureka'
        LISBON = 'Lisbon', 'Lisbon'
        OTHER = 'Other', 'Other'

    lot_no = models.CharField(max_length=30, help_text='Famous lot id, unique within a plant.')
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name='lots')
    grower = models.ForeignKey(Grower, on_delete=models.PROTECT, related_name='lots')
    block = models.CharField(max_length=50, blank=True)
    variety = models.CharField(max_length=10, choices=Variety.choices, default=Variety.LISBON)
    harvest_date = models.DateField(
        null=True,
        blank=True,
        help_text='Harvest date when known. This separates preharvest maturity from storage time.',
    )
    receive_date = models.DateField()
    receiving_color = models.CharField(max_length=2, choices=Color.choices, default=Color.DARK_GREEN)
    intake_cci_mean = models.FloatField(
        null=True,
        blank=True,
        help_text='Measured mean CCI at receipt; preferred over the categorical receiving color.',
    )
    intake_cci_std = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Within-lot CCI standard deviation at receipt.',
    )
    bins_received = models.PositiveIntegerField(null=True, blank=True)
    current_room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='lots'
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_STORAGE)
    packed_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    objects = LotQuerySet.as_manager()

    class Meta:
        ordering = ['plant__code', 'receive_date', 'lot_no']
        constraints = [
            models.UniqueConstraint(fields=['plant', 'lot_no'], name='unique_lot_per_plant'),
            models.CheckConstraint(
                condition=(Q(status='packed', packed_date__isnull=False) | ~Q(status='packed')),
                name='packed_lot_has_packed_date',
            ),
            models.CheckConstraint(
                condition=(Q(status='packed') | Q(packed_date__isnull=True)),
                name='unpacked_lot_has_no_packed_date',
            ),
        ]
        indexes = [models.Index(fields=['plant', 'status'])]

    def __str__(self):
        return f'{self.plant.code} {self.lot_no}'

    def delete(self, *args, **kwargs):
        raise ValidationError('Lots are never deleted. Set status to packed or dumped instead.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.current_room_id and self.current_room.plant_id != self.plant_id:
            errors['current_room'] = 'The current room must belong to the lot\'s plant.'
        if self.status == self.Status.PACKED and not self.packed_date:
            errors['packed_date'] = 'A packed lot requires a packed date.'
        if self.status != self.Status.PACKED and self.packed_date:
            errors['packed_date'] = 'Only a packed lot may have a packed date.'
        if self.harvest_date and self.receive_date and self.harvest_date > self.receive_date:
            errors['harvest_date'] = 'Harvest date cannot be after receipt.'
        if errors:
            raise ValidationError(errors)

    @property
    def end_date(self):
        if self.status == self.Status.PACKED and self.packed_date:
            return self.packed_date
        return timezone.localdate()

    @property
    def days_in_storage(self):
        return (self.end_date - self.receive_date).days

    @property
    def weeks_in_storage(self):
        return round(self.days_in_storage / 7, 1)

    @property
    def bins_packed(self):
        """Known packed bins, or None when any packout omitted bin usage."""
        packouts = list(self.packouts.all())
        if not packouts:
            return Decimal('0')
        if any(p.bins_packed is None for p in packouts):
            return None
        return sum((p.bins_packed for p in packouts), Decimal('0'))

    @property
    def bins_remaining(self):
        """Best known on-hand bins. None means quantity reconciliation is incomplete."""
        if self.bins_received is None:
            return None
        packed = self.bins_packed
        if packed is None:
            return None
        return Decimal(self.bins_received) - packed

    @property
    def is_partially_packed(self):
        return self.status == self.Status.IN_STORAGE and bool(list(self.packouts.all()))


class LotRoomMove(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='room_moves')
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='moves_in')
    moved_at = models.DateField()
    moved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['-moved_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'room', 'moved_at'], name='unique_room_move_per_lot_day'
            )
        ]

    def __str__(self):
        return f'{self.lot} -> {self.room} on {self.moved_at}'

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.lot_id and self.room_id and self.lot.plant_id != self.room.plant_id:
            errors['room'] = 'The room must belong to the lot\'s plant.'
        if self.lot_id and self.moved_at and self.moved_at < self.lot.receive_date:
            errors['moved_at'] = 'A room move cannot precede receipt.'
        if self.lot_id and self.lot.packed_date and self.moved_at > self.lot.packed_date:
            errors['moved_at'] = 'A room move cannot occur after final packout.'
        if errors:
            raise ValidationError(errors)


class ImportBatch(models.Model):
    """One uploaded CSV. Row-level problems never abort the import; they land
    in error_report as [{"row": n, "error": "..."}] and the good rows go in."""

    class Kind(models.TextChoices):
        RECEIVING = 'receiving', 'Receiving'
        PACKOUT = 'packout', 'Packout'
        ROOM_MOVES = 'room_moves', 'Room moves'
        CONDITIONS = 'conditions', 'Room conditions'
        TREATMENTS = 'treatments', 'Lot treatments'

    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(upload_to='imports/%Y/%m/', blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    plant_scope = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='import_batches',
        help_text='Plant enforced for a pinned uploader; blank means an authorized multi-plant batch.',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    rows_ok = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)
    error_report = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name_plural = 'import batches'

    def __str__(self):
        return f'{self.get_kind_display()} {self.original_name} ({self.uploaded_at:%Y-%m-%d %H:%M})'

    @property
    def rows_total(self):
        return self.rows_ok + self.rows_failed


class RoomCondition(models.Model):
    """A raw timestamped room reading used to reconstruct lot exposure."""

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='conditions')
    recorded_at = models.DateTimeField()
    temperature_f = models.DecimalField(max_digits=6, decimal_places=2)
    relative_humidity_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    ethylene_ppm = models.DecimalField(
        max_digits=9,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    co2_pct = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    source = models.CharField(max_length=80, default='csv')
    source_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='room_conditions',
    )

    class Meta:
        ordering = ['room', 'recorded_at']
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'recorded_at', 'source'],
                name='unique_room_condition_reading',
            )
        ]
        indexes = [models.Index(fields=['room', 'recorded_at'])]

    def __str__(self):
        return f'{self.room} {self.recorded_at:%Y-%m-%d %H:%M}: {self.temperature_f} F'

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class LotTreatment(models.Model):
    class TreatmentType(models.TextChoices):
        ETHYLENE = 'ethylene', 'Ethylene degreening'
        WAX = 'wax', 'Wax or coating'
        FUNGICIDE = 'fungicide', 'Fungicide'
        ONE_MCP = '1_mcp', '1-MCP'
        GA3 = 'ga3', 'Gibberellic acid (GA3)'
        TWO_FOUR_D = '2_4_d', '2,4-D'
        OTHER = 'other', 'Other'

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='treatments')
    applied_at = models.DateTimeField()
    treatment_type = models.CharField(max_length=12, choices=TreatmentType.choices)
    product = models.CharField(max_length=100, blank=True)
    concentration = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    concentration_unit = models.CharField(
        max_length=20,
        blank=True,
        help_text='For example ppm, percent, oz/gal, or label rate.',
    )
    duration_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    notes = models.CharField(max_length=250, blank=True)
    source_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lot_treatments',
    )

    class Meta:
        ordering = ['lot', 'applied_at']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'applied_at', 'treatment_type', 'product'],
                name='unique_lot_treatment_event',
            )
        ]
        indexes = [models.Index(fields=['lot', 'applied_at'])]

    def __str__(self):
        return f'{self.lot} {self.get_treatment_type_display()} {self.applied_at:%Y-%m-%d}'

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.lot_id and self.applied_at:
            applied_on = timezone.localtime(self.applied_at).date()
            if applied_on < self.lot.receive_date:
                raise ValidationError({'applied_at': 'Treatment cannot precede receipt.'})
            if self.lot.packed_date and applied_on > self.lot.packed_date:
                raise ValidationError({'applied_at': 'Treatment cannot occur after final packout.'})


class Packout(models.Model):
    """What actually packed out of the lot. One row per lot per pack date, so
    a lot packed across two runs has two rows."""

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='packouts')
    packed_date = models.DateField()
    cartons_fancy = models.PositiveIntegerField(default=0)
    cartons_choice = models.PositiveIntegerField(default=0)
    cartons_standard = models.PositiveIntegerField(default=0)
    cartons_products = models.PositiveIntegerField(default=0)
    bins_packed = models.DecimalField(
        max_digits=9,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Bins consumed by this run. Required for an on-hand inventory balance.',
    )
    is_final = models.BooleanField(
        default=True,
        help_text='Final packout closes the lot. Clear this for a partial run with fruit remaining.',
    )
    packout_color = models.CharField(
        max_length=2,
        choices=Color.choices,
        blank=True,
        help_text='Observed lot color at packout; this is a direct model-validation label.',
    )
    decay_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Observed decay percent at packout.',
    )
    soft_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Observed soft fruit percent at packout.',
    )
    shrivel_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Observed shriveled fruit percent at packout.',
    )
    chilling_injury_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Observed chilling injury percent at packout.',
    )
    meets_spec = models.BooleanField(
        null=True,
        blank=True,
        help_text='Whether the run met the intended customer or house quality specification.',
    )
    downgrade_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text='Why fruit went to products (color, decay, size, market, etc.).',
    )
    cartons_total = models.PositiveIntegerField(default=0, editable=False)
    fresh_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, editable=False
    )
    source_batch = models.ForeignKey(
        ImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='packouts'
    )

    class Meta:
        ordering = ['-packed_date']
        constraints = [models.UniqueConstraint(fields=['lot', 'packed_date'], name='one_packout_per_lot_day')]

    def __str__(self):
        return f'{self.lot} packed {self.packed_date}'

    @property
    def cartons_fresh(self):
        return self.cartons_fancy + self.cartons_choice + self.cartons_standard

    def compute(self):
        self.cartons_total = self.cartons_fresh + self.cartons_products
        if self.cartons_total:
            self.fresh_pct = round(100 * self.cartons_fresh / self.cartons_total, 2)
        else:
            self.fresh_pct = None

    def save(self, *args, **kwargs):
        self.full_clean(exclude=['cartons_total', 'fresh_pct'])
        self.compute()
        super().save(*args, **kwargs)
        self.reconcile_lot_status()

    def delete(self, *args, **kwargs):
        lot_id = self.lot_id
        result = super().delete(*args, **kwargs)
        self.reconcile_lot_status(lot_id=lot_id)
        return result

    def reconcile_lot_status(self, lot_id=None):
        lot = Lot.objects.get(pk=lot_id or self.lot_id)
        final = Packout.objects.filter(lot=lot, is_final=True).order_by('-packed_date').first()
        if final is not None:
            Lot.objects.filter(pk=lot.pk).update(
                status=Lot.Status.PACKED,
                packed_date=final.packed_date,
            )
        elif lot.status == Lot.Status.PACKED:
            Lot.objects.filter(pk=lot.pk).update(
                status=Lot.Status.IN_STORAGE,
                packed_date=None,
            )

    def clean(self):
        errors = {}
        if self.lot_id and self.packed_date and self.packed_date < self.lot.receive_date:
            errors['packed_date'] = 'Packout cannot precede receipt.'
        if self.lot_id and self.bins_packed is not None and self.lot.bins_received is not None:
            other_bins = sum(
                (
                    p.bins_packed for p in Packout.objects.filter(lot_id=self.lot_id)
                    .exclude(pk=self.pk)
                    if p.bins_packed is not None
                ),
                Decimal('0'),
            )
            if other_bins + self.bins_packed > Decimal(self.lot.bins_received):
                errors['bins_packed'] = (
                    f'Cumulative packed bins would exceed {self.lot.bins_received} received bins.'
                )
        if errors:
            raise ValidationError(errors)


class UserProfile(models.Model):
    """Which plant a user belongs to. Foremen must have one; GMs and admins
    with no plant see every plant."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, null=True, blank=True, related_name='users')

    def __str__(self):
        return f'{self.user} @ {self.plant or "all plants"}'


def plant_for(user):
    """The plant a user is pinned to, or None for all-plant users."""
    try:
        return user.profile.plant
    except UserProfile.DoesNotExist:
        return None


class ModelSettings(models.Model):
    """Singleton: thresholds, priors and buffers that must be tunable without
    a deploy. Calibrate against foreman calls in weeks 1-3. Fetch with
    ModelSettings.get()."""

    cci_dg_max = models.FloatField(default=-7.0, help_text='Mean CCI below this is dark green.')
    cci_lg_max = models.FloatField(default=-3.0, help_text='Mean CCI at or below this (and above DG) is light green.')
    cci_s_max = models.FloatField(default=2.0, help_text='Mean CCI at or below this (and above LG) is silver. Above is yellow.')

    prior_drift_dg = models.FloatField(default=0.10, help_text='CCI per day for lots received dark green (55 F).')
    prior_drift_lg = models.FloatField(default=0.15)
    prior_drift_s = models.FloatField(default=0.25)
    prior_drift_y = models.FloatField(default=0.25)

    start_cci_dg = models.FloatField(default=-10.0, help_text='Assumed CCI at receipt for an unsampled dark green lot.')
    start_cci_lg = models.FloatField(default=-5.0)
    start_cci_s = models.FloatField(default=-0.5)
    start_cci_y = models.FloatField(default=4.0)

    buffer_days = models.PositiveIntegerField(default=7, help_text='pack_by = predicted yellow date minus this.')
    decay_flag_pct = models.FloatField(default=2.0, help_text='Decay rate (percent) at or above which the lot is flagged.')
    min_fruit_for_score = models.PositiveIntegerField(default=6, help_text='Photos with fewer detected fruit are marked failed.')
    max_horizon_days = models.PositiveIntegerField(
        default=365, help_text='Cap on how far ahead a yellow date is projected when drift is tiny.'
    )
    sample_overdue_days = models.PositiveIntegerField(default=10)
    import_gap_days = models.PositiveIntegerField(default=120)

    class Meta:
        verbose_name = 'model settings'
        verbose_name_plural = 'model settings'

    def __str__(self):
        return 'Model settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if not self.cci_dg_max < self.cci_lg_max < self.cci_s_max:
            errors['cci_s_max'] = 'CCI thresholds must increase from dark green to yellow.'
        for field in ('prior_drift_dg', 'prior_drift_lg', 'prior_drift_s', 'prior_drift_y'):
            if getattr(self, field) <= 0:
                errors[field] = 'Prior drift must be greater than zero.'
        if not 1 <= self.min_fruit_for_score <= 10:
            errors['min_fruit_for_score'] = 'Use between 1 and 10 fruit.'
        if not 0 <= self.decay_flag_pct <= 100:
            errors['decay_flag_pct'] = 'Decay alert percent must be between 0 and 100.'
        if self.max_horizon_days < 1:
            errors['max_horizon_days'] = 'Forecast horizon must be at least one day.'
        if errors:
            raise ValidationError(errors)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # -- helpers used by scoring and prediction --

    def stage_for(self, cci):
        if cci is None:
            return None
        if cci < self.cci_dg_max:
            return Color.DARK_GREEN
        if cci <= self.cci_lg_max:
            return Color.LIGHT_GREEN
        if cci <= self.cci_s_max:
            return Color.SILVER
        return Color.YELLOW

    @property
    def yellow_threshold(self):
        return self.cci_s_max

    def prior_drift(self, receiving_color):
        return {
            Color.DARK_GREEN: self.prior_drift_dg,
            Color.LIGHT_GREEN: self.prior_drift_lg,
            Color.SILVER: self.prior_drift_s,
            Color.YELLOW: self.prior_drift_y,
        }.get(receiving_color, self.prior_drift_dg)

    def start_cci(self, receiving_color):
        return {
            Color.DARK_GREEN: self.start_cci_dg,
            Color.LIGHT_GREEN: self.start_cci_lg,
            Color.SILVER: self.start_cci_s,
            Color.YELLOW: self.start_cci_y,
        }.get(receiving_color, self.start_cci_dg)

    def thresholds_dict(self):
        return {'dg_max': self.cci_dg_max, 'lg_max': self.cci_lg_max, 's_max': self.cci_s_max}
