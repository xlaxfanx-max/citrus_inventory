"""Observable preparation evidence, deliberately separate from model accuracy."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from lots.models import ImportBatch, Lot, LotRoomMove, Packout, ModelSettings, Room
from lots.planning import board_rows, plan_lots
from sampling.models import BoardCalibration, Sample, SamplePhoto


def readiness_for(plant, today=None):
    today = today or timezone.localdate()
    lots = Lot.objects.at_plant(plant)
    samples = Sample.objects.filter(lot__in=lots, is_void=False)
    photos = SamplePhoto.objects.filter(sample__in=samples)
    rows = board_rows(plan_lots(plant, today), today, ModelSettings.get())
    packouts = Packout.objects.filter(lot__in=lots, is_final=True)
    labelled = packouts.filter(Q(packout_color__gt='') | Q(decay_pct__isnull=False) | Q(meets_spec__isnull=False)).count()
    cal = BoardCalibration.objects.filter(plant=plant, active=True).count() if plant else 0
    calibrated_photos = photos.exclude(calibration_snapshot={}).count()
    moves = LotRoomMove.objects.filter(lot__in=lots)
    imports = ImportBatch.objects.filter(Q(plant_scope=plant) | Q(plant_scope__isnull=True))
    latest_upload = imports.first()
    recent_upload = bool(latest_upload and (timezone.now() - latest_upload.uploaded_at).total_seconds() < 86400)
    holdouts = samples.filter(purpose=Sample.Purpose.HOLDOUT).count()
    timings = sorted(
        samples.filter(capture_seconds__isnull=False, sampled_at__gte=timezone.now() - timedelta(days=30))
        .values_list('capture_seconds', flat=True)
    )
    if timings:
        mid = len(timings) // 2
        median = timings[mid] if len(timings) % 2 else (timings[mid - 1] + timings[mid]) / 2
        capture_value = f'{round(median)} s median · {len(timings)} samples in 30 days · target 90 s'
    else:
        capture_value = 'No timed samples yet'
    settings = ModelSettings.get()
    rooms_without_setpoint = Room.objects.filter(plant=plant, target_temp_f__isnull=True).count() if plant else Room.objects.filter(target_temp_f__isnull=True).count()
    rooms_total = Room.objects.filter(plant=plant).count() if plant else Room.objects.count()
    return {
        'rows': rows,
        'checks': [
            ('Routine forecast evidence', f'{sum(r["dates_usable"] for r in rows)} / {len(rows)} active lots',
             'Current forecasts need usable routine observations on two separate days. This checks evidence availability, not biological accuracy.'),
            ('Capture time', capture_value,
             'Seconds from opening the capture screen to saving, measured by the app. It excludes walking to the bins and pulling fruit; time the whole route separately.'),
            ('Room setpoints', f'{rooms_total - rooms_without_setpoint} / {rooms_total} rooms',
             f'The rot-risk clock counts weeks at or above {settings.warm_storage_temp_c:g} °C and the temperature response scales prior degreening rates. Both need each room\'s target temperature in Administration.'),
            ('Station calibration records', f'{cal} active setups; {calibrated_photos} photos with references',
             'Instrument-measured board, phone and light references can be registered in Admin. Independent agreement and repeatability still require field testing.'),
            ('Direct final-packout labels', f'{labelled} / {packouts.count()} final packouts',
             'Record observed color, decay or specification result. A management packing date is not a biological failure date.'),
            ('Shelf-life holdouts', f'{holdouts} assessments',
             'Follow the same identified fruit and document its storage/handling conditions. Holdouts do not feed the routine forecast.'),
            ('Room-move precision', f'{moves.filter(occurred_at__isnull=False).count()} timestamped; {moves.filter(occurred_at__isnull=True).count()} date only',
             'Date-only moves remain visibly approximate. A current location alone is not reconstructed as past exposure.'),
            ('Source upload freshness', 'Upload within 24 hours' if recent_upload else 'No upload within 24 hours',
             'Upload time alone does not verify source freshness or reconciled stock. Confirm the source extract time and quantities with the inventory owner.'),
        ],
        'latest_upload': latest_upload,
        'blocked_count': sum(bool(r['evidence_notes']) for r in rows),
    }
