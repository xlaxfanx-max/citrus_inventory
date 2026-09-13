"""Weekly samples: the foreman's three taps plus one or two photos of ten
fruit on the reference board. Photos are scored in the background by
`manage.py score_photos`; everything the pipeline measures is stored raw so a
better pipeline can re-score later.

Foreman fields (color, pack-within, decay count) are the baseline the model
is judged against. They are never model inputs and the admin refuses to edit
them after the fact.
"""

from datetime import timezone as datetime_timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext as _
import math

from lots.models import Color, Lot


class BoardCalibration(models.Model):
    """Instrument-measured references for one station setup; versions are immutable."""

    plant = models.ForeignKey('lots.Plant', on_delete=models.PROTECT)
    board_id = models.CharField(max_length=80)
    phone_id = models.CharField(max_length=80)
    light_id = models.CharField(max_length=80)
    measured_at = models.DateTimeField()
    instrument = models.CharField(max_length=200, help_text='Instrument, illuminant and measurement record identifier.')
    reference_rgb = models.JSONField(help_text='All nine patch names mapped to measured D65 sRGB values [R,G,B], each 0–255. Never enter nominal print targets as measurements.')
    device_model = models.CharField(max_length=80, blank=True, help_text='Phone make and model, e.g. iPhone 15 or Pixel 8a. Camera response differs by device.')
    white_balance_mode = models.CharField(max_length=40, blank=True, help_text='White-balance setting locked on the phone camera, e.g. Daylight or 5000K. Auto white balance shifts color between shots and must not be used.')
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-measured_at', '-pk']

    def __str__(self):
        return f'{self.board_id} / {self.phone_id} / {self.measured_at:%Y-%m-%d}'

    def clean(self):
        from .board import patches
        expected = {p['name'] for p in patches()}
        valid = isinstance(self.reference_rgb, dict) and set(self.reference_rgb) == expected
        if valid:
            valid = all(isinstance(rgb, list) and len(rgb) == 3 and all(
                isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 255
                for v in rgb
            ) for rgb in self.reference_rgb.values())
        if not valid:
            raise ValidationError({'reference_rgb': 'Provide measured RGB triples for exactly the nine board patches.'})
        if self.measured_at and self.measured_at > timezone.now():
            raise ValidationError({'measured_at': 'A measurement cannot be in the future.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            if old.snapshot() != self.snapshot():
                raise ValidationError('Calibration records are immutable. Create a new measured version and retire the old one.')
        super().save(*args, **kwargs)

    def snapshot(self):
        return {'calibration_id': self.pk, 'plant_id': self.plant_id, 'board_id': self.board_id,
                'phone_id': self.phone_id, 'light_id': self.light_id,
                'device_model': self.device_model, 'white_balance_mode': self.white_balance_mode,
                'measured_at': self.measured_at.astimezone(datetime_timezone.utc).isoformat(), 'instrument': self.instrument,
                'reference_rgb': self.reference_rgb}


class Sample(models.Model):
    class SelectionMethod(models.TextChoices):
        ACROSS_BINS = 'across_bins', 'Random fruit across bins'
        FIXED_HOLDOUT = 'fixed_holdout', 'Fixed holdout group'
        CONVENIENCE = 'convenience', 'Convenience sample'
        UNKNOWN = 'unknown', 'Not recorded'

    class Purpose(models.TextChoices):
        ROUTINE = 'routine', 'Routine monitoring'
        HOLDOUT = 'holdout', 'Shelf-life holdout'

    class Marketability(models.TextChoices):
        PASS = 'pass', 'Meets pack specification'
        FAIL = 'fail', 'Failed pack specification'

    class FailureReason(models.TextChoices):
        COLOR = 'color', 'Color'
        DECAY = 'decay', 'Decay'
        SHRIVEL = 'shrivel', 'Shrivel'
        SOFT = 'soft', 'Softness'
        CHILLING = 'chilling', 'Chilling injury'
        RIND = 'rind', 'Rind breakdown'
        OTHER = 'other', 'Other'

    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name='samples')
    sampled_at = models.DateTimeField(default=timezone.now)
    sampled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    foreman_color = models.CharField(max_length=2, choices=Color.choices)
    foreman_pack_within_weeks = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(8)]
    )
    decay_count = models.PositiveSmallIntegerField(default=0)
    fruit_count = models.PositiveSmallIntegerField(default=10)
    selection_method = models.CharField(
        max_length=16,
        choices=SelectionMethod.choices,
        default=SelectionMethod.UNKNOWN,
    )
    sampled_bins_count = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
    )
    purpose = models.CharField(max_length=8, choices=Purpose.choices, default=Purpose.ROUTINE)
    soft_count = models.PositiveSmallIntegerField(default=0)
    shrivel_count = models.PositiveSmallIntegerField(default=0)
    chilling_injury_count = models.PositiveSmallIntegerField(default=0)
    rind_breakdown_count = models.PositiveSmallIntegerField(default=0)
    firmness_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[
            (1, '1 — soft'),
            (2, '2 — yielding'),
            (3, '3 — fairly firm'),
            (4, '4 — firm'),
            (5, '5 — very firm'),
        ],
    )
    marketability = models.CharField(
        max_length=4,
        choices=Marketability.choices,
        blank=True,
        help_text='Required for shelf-life holdout assessments.',
    )
    failure_reason = models.CharField(
        max_length=10,
        choices=FailureReason.choices,
        blank=True,
    )
    notes = models.TextField(blank=True)
    capture_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Seconds from opening the capture screen to saving. The pilot target is a 90-second median.',
    )
    is_void = models.BooleanField(
        default=False,
        help_text='Voided samples remain in the audit trail but are excluded from forecasts.',
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='voided_lemon_samples',
    )
    void_reason = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ['-sampled_at', '-id']
        indexes = [models.Index(fields=['lot', 'sampled_at'])]
        constraints = [
            models.CheckConstraint(
                condition=Q(decay_count__lte=F('fruit_count')),
                name='sample_decay_not_above_fruit_count',
            ),
            models.CheckConstraint(
                condition=Q(soft_count__lte=F('fruit_count')),
                name='sample_soft_not_above_fruit_count',
            ),
            models.CheckConstraint(
                condition=Q(shrivel_count__lte=F('fruit_count')),
                name='sample_shrivel_not_above_fruit_count',
            ),
            models.CheckConstraint(
                condition=Q(chilling_injury_count__lte=F('fruit_count')),
                name='sample_chilling_not_above_fruit_count',
            ),
            models.CheckConstraint(
                condition=Q(rind_breakdown_count__lte=F('fruit_count')),
                name='sample_rind_not_above_fruit_count',
            ),
        ]

    def __str__(self):
        return f'{self.lot} sample {self.sampled_at:%Y-%m-%d}'

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        for field in (
            'decay_count', 'soft_count', 'shrivel_count',
            'chilling_injury_count', 'rind_breakdown_count',
        ):
            if getattr(self, field) > self.fruit_count:
                errors[field] = 'Defect count cannot exceed the sampled fruit count.'
        if self.lot_id and self.sampled_on < self.lot.receive_date:
            errors['sampled_at'] = 'A sample cannot precede receipt.'
        if self.is_void and not self.void_reason:
            errors['void_reason'] = 'A reason is required when voiding a sample.'
        if self.purpose == self.Purpose.HOLDOUT and not self.marketability:
            errors['marketability'] = 'A holdout assessment must record whether the fruit still meets specification.'
        if self.marketability == self.Marketability.FAIL and not self.failure_reason:
            errors['failure_reason'] = 'Record the limiting reason when a holdout fails specification.'
        if self.marketability != self.Marketability.FAIL and self.failure_reason:
            errors['failure_reason'] = 'A failure reason is only valid for a failed holdout assessment.'
        if errors:
            raise ValidationError(errors)

    @property
    def sampled_on(self):
        return timezone.localtime(self.sampled_at).date()

    @property
    def foreman_pack_by_date(self):
        """The foreman's 'pack within N weeks' turned into a date."""
        return self.sampled_on + timezone.timedelta(weeks=self.foreman_pack_within_weeks)

    @property
    def foreman_pack_label(self):
        if self.foreman_pack_within_weeks == 0:
            return _('Today')
        return _('Within %(n)d wk') % {'n': self.foreman_pack_within_weeks}

    @property
    def decay_pct(self):
        return 100 * self.decay_count / self.fruit_count if self.fruit_count else None

    @property
    def defect_summary(self):
        """Non-zero defect counts only, e.g. 'decay 2 · soft 1 of 25'; 'none' when clean."""
        parts = [
            (label, count) for label, count in (
                ('decay', self.decay_count), ('soft', self.soft_count), ('shrivel', self.shrivel_count),
                ('chilling', self.chilling_injury_count), ('rind', self.rind_breakdown_count),
            ) if count
        ]
        if not parts:
            return f'none of {self.fruit_count}'
        return ' · '.join(f'{label} {count}' for label, count in parts) + f' of {self.fruit_count}'

    @property
    def best_photo(self):
        scored = [
            p for p in self.photos.all()
            if p.status == SamplePhoto.Status.SCORED and p.quality_ok
        ]
        if scored:
            return max(scored, key=lambda p: p.fruit_detected)
        photos = list(self.photos.all())
        return photos[0] if photos else None

    @property
    def mean_cci(self):
        """Mean CCI across this sample's scored photos (usually one)."""
        vals = [
            p.mean_cci for p in self.photos.all()
            if p.status == SamplePhoto.Status.SCORED and p.quality_ok and p.mean_cci is not None
        ]
        return sum(vals) / len(vals) if vals else None

    @property
    def cci_distribution(self):
        """Robust per-fruit color summary across every usable photo."""
        # The pipeline stores None for a fruit whose b* is too close to zero
        # to give a usable CCI; those fruit are simply not part of the sample.
        values = sorted(
            float(value)
            for photo in self.photos.all()
            if photo.status == SamplePhoto.Status.SCORED and photo.quality_ok
            for value in (photo.per_fruit_cci or [])
            if value is not None
        )
        if not values:
            return None

        def percentile(fraction):
            position = (len(values) - 1) * fraction
            lower = int(position)
            upper = min(lower + 1, len(values) - 1)
            weight = position - lower
            return values[lower] * (1 - weight) + values[upper] * weight

        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return {
            'n': len(values),
            'mean': round(mean, 3),
            'p10': round(percentile(0.10), 3),
            'median': round(percentile(0.50), 3),
            'p90': round(percentile(0.90), 3),
            'std': round(variance ** 0.5, 3),
        }


def photo_upload_path(instance, filename):
    lot = instance.sample.lot
    stamp = timezone.now().strftime('%Y%m%d-%H%M%S')
    ext = (filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg').lower()[:5]
    return f'photos/{lot.plant.code}/{lot.lot_no}/{stamp}-{instance.sample_id}.{ext}'


class SamplePhoto(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SCORED = 'scored', 'Scored'
        FAILED = 'failed', 'Failed'

    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name='photos')
    image = models.FileField(upload_to=photo_upload_path)
    calibration_snapshot = models.JSONField(default=dict, blank=True, help_text='Station and measured references copied at capture; retained when rescoring.')
    thumb = models.FileField(upload_to='thumbs/%Y/%m/', blank=True, help_text='Small JPEG made by the scoring job for the board.')
    device_info = models.CharField(max_length=200, blank=True, help_text='Browser user agent at upload, so photos can be grouped by phone when reviewing calibration.')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    card_detected = models.BooleanField(default=False)
    fruit_detected = models.PositiveSmallIntegerField(default=0)
    per_fruit_lab = models.JSONField(default=list, blank=True)
    per_fruit_cci = models.JSONField(default=list, blank=True)
    mean_cci = models.FloatField(null=True, blank=True)
    std_cci = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)
    pipeline_version = models.CharField(max_length=40, blank=True)
    scoring_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Board markers, correction matrix, patch diagnostics and blob centers.',
    )
    quality_ok = models.BooleanField(default=True)
    quality_warnings = models.JSONField(default=list, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at', '-id']
        indexes = [models.Index(fields=['status', 'uploaded_at'])]

    def __str__(self):
        return f'{self.sample} photo {self.pk} ({self.status})'

    @property
    def storage_path(self):
        return self.image.name

    def mark_failed(self, error, **measured):
        self.status = self.Status.FAILED
        self.error = error[:2000]
        self.processed_at = timezone.now()
        self.processing_started_at = None
        for k, v in measured.items():
            setattr(self, k, v)
        self.save()

    def mark_scored(self, result, version):
        correction = result.get('correction') or {}
        warnings = []
        if not self.calibration_snapshot:
            warnings.append('No instrument-measured station calibration; exploratory color measurement only.')
        if not correction.get('applied'):
            warnings.append('color correction was not reliable; excluded from forecasting')
        if result['fruit_detected'] < 10:
            warnings.append(f'only {result["fruit_detected"]} of 10 fruit were measured')
        if result['std_cci'] > 3.0:
            warnings.append(f'high within-photo CCI variation ({result["std_cci"]:.2f})')
        self.status = self.Status.SCORED
        self.error = ''
        self.processed_at = timezone.now()
        self.processing_started_at = None
        self.card_detected = True
        self.fruit_detected = result['fruit_detected']
        self.per_fruit_lab = result['per_fruit_lab']
        self.per_fruit_cci = result['per_fruit_cci']
        self.mean_cci = result['mean_cci']
        self.std_cci = result['std_cci']
        self.pipeline_version = version
        self.scoring_metadata = {
            'calibration': self.calibration_snapshot or {'status': 'nominal_print_targets'},
            'markers': result.get('markers', []),
            'correction': correction,
            'blob_centers': result.get('blob_centers', []),
        }
        self.quality_ok = bool(correction.get('applied'))
        self.quality_warnings = warnings
        self.save()

    def mark_retry(self, error):
        self.status = self.Status.PENDING
        self.error = error[:2000]
        self.processing_started_at = None
        self.save(update_fields=['status', 'error', 'processing_started_at'])
