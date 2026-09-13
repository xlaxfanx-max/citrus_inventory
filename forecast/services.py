"""Database-aware wrappers around forecast.model: gather a lot's scored
points and decay counts, run the model, upsert the Prediction row."""

from lots.models import Lot, ModelSettings
from sampling.models import Sample, SamplePhoto
from django.utils import timezone

from .model import predict
from .models import Prediction
from .features import features_for_lot, warm_exposure


def lot_points_with_sources(lot, up_to=None):
    """Return model points plus the sample/photo provenance for each point."""
    samples = Sample.objects.filter(lot=lot, is_void=False, purpose=Sample.Purpose.ROUTINE).prefetch_related('photos').order_by('sampled_at')
    points = []
    sources = []
    for s in samples:
        if up_to is not None and s.sampled_on > up_to:
            continue
        usable_photos = [
            p for p in s.photos.all()
            if p.status == SamplePhoto.Status.SCORED and p.quality_ok and p.mean_cci is not None
        ]
        vals = [p.mean_cci for p in usable_photos]
        if vals:
            point = ((s.sampled_on - lot.receive_date).days, sum(vals) / len(vals))
            distribution = s.cci_distribution
            points.append(point)
            sources.append({
                'sample_id': s.pk,
                'sampled_on': s.sampled_on.isoformat(),
                'photo_ids': [p.pk for p in usable_photos],
                'pipeline_versions': sorted({p.pipeline_version for p in usable_photos}),
                'mean_cci': round(point[1], 3),
                'cci_distribution': distribution,
                'selection_method': s.selection_method,
                'sampled_bins_count': s.sampled_bins_count,
                'quality': {
                    'decay_count': s.decay_count,
                    'soft_count': s.soft_count,
                    'shrivel_count': s.shrivel_count,
                    'chilling_injury_count': s.chilling_injury_count,
                    'rind_breakdown_count': s.rind_breakdown_count,
                    'firmness_score': s.firmness_score,
                    'purpose': s.purpose,
                    'marketability': s.marketability or None,
                    'failure_reason': s.failure_reason or None,
                },
            })
    return points, sources


def lot_points(lot, up_to=None):
    """[(days_since_receive, mean_cci)] from every usable, non-void sample."""
    return lot_points_with_sources(lot, up_to=up_to)[0]


def lot_decay_samples(lot, up_to=None):
    qs = Sample.objects.filter(lot=lot, is_void=False, purpose=Sample.Purpose.ROUTINE).order_by('-sampled_at')
    out = []
    for s in qs:
        if up_to is not None and s.sampled_on > up_to:
            continue
        out.append((s.decay_count, s.fruit_count))
        if len(out) == 2:
            break
    return list(reversed(out))


def rebuild_for_lot(lot, as_of=None, settings=None):
    as_of = as_of or timezone.localdate()
    settings = settings or ModelSettings.get()
    points, point_sources = lot_points_with_sources(lot, up_to=as_of)
    result = predict(
        as_of=as_of,
        receive_date=lot.receive_date,
        receiving_color=lot.receiving_color,
        points=points,
        decay_samples=lot_decay_samples(lot, up_to=as_of),
        settings=settings,
        room_temp_c=lot.current_room.setpoint_c if lot.current_room else None,
    )
    result['inputs']['point_sources'] = point_sources
    result['inputs']['features'] = features_for_lot(lot, as_of)
    result['inputs']['warm_storage'] = warm_exposure(lot, as_of, settings)
    pred, _ = Prediction.objects.update_or_create(lot=lot, as_of_date=as_of, defaults=result)
    return pred


def rebuild_all(plant=None, as_of=None, settings=None):
    settings = settings or ModelSettings.get()
    lots = Lot.objects.in_storage().at_plant(plant).select_related('plant')
    n = 0
    for lot in lots:
        rebuild_for_lot(lot, as_of=as_of, settings=settings)
        n += 1
    return n
