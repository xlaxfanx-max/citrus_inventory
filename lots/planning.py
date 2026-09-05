"""The ranked packing plan: one row per in-storage lot with the next action
the plant should take, shared by the board view and the versioned plan
snapshots in forecast.plans.

Each action has a stable code (stored on PlanRecommendation), the label the
board shows, a tone for styling, and a rank that orders the board. The
three rank 0-1 actions are the ones management must record a decision on.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Prefetch

from forecast.models import PlanAction, Prediction
from sampling.models import Sample, SamplePhoto

from .models import Lot


@dataclass(frozen=True)
class Action:
    code: str
    label: str
    tone: str
    rank: int
    requires_decision: bool = False


def _action(member, tone, rank, requires_decision=False):
    return Action(member.value, member.label, tone, rank, requires_decision)


DECAY_RISK = _action(PlanAction.DECAY_RISK, 'red', 0, True)
PACK_OVERDUE = _action(PlanAction.PACK_OVERDUE, 'red', 0, True)
PACK_THIS_WEEK = _action(PlanAction.PACK_THIS_WEEK, 'red', 1, True)
RETAKE_PHOTO = _action(PlanAction.RETAKE_PHOTO, 'amber', 2)
SAMPLE_DUE = _action(PlanAction.SAMPLE_DUE, 'amber', 3)
PACK_SOON = _action(PlanAction.PACK_SOON, 'amber', 4)
SCORING = _action(PlanAction.SCORING, 'grey', 5)
NEEDS_BASELINE = _action(PlanAction.NEEDS_BASELINE, 'grey', 5)
MONITOR = _action(PlanAction.MONITOR, 'ok', 6)

ACTIONS = [DECAY_RISK, PACK_OVERDUE, PACK_THIS_WEEK, RETAKE_PHOTO, SAMPLE_DUE, PACK_SOON, SCORING, NEEDS_BASELINE, MONITOR]
ACTION_BY_CODE = {a.code: a for a in ACTIONS}


def plan_lots(plant):
    """In-storage lots at a plant with everything the ranking needs prefetched."""
    return (
        Lot.objects.in_storage().at_plant(plant)
        .select_related('grower', 'current_room', 'plant')
        .prefetch_related(
            Prefetch('predictions', queryset=Prediction.objects.latest_per_lot()),
            Prefetch(
                'samples',
                queryset=Sample.objects.filter(is_void=False).order_by('-sampled_at', '-id').prefetch_related('photos'),
            ),
            'packouts',
        )
    )


def board_rows(lots, today, settings):
    rows = []
    for lot in lots:
        pred = next(iter(lot.predictions.all()), None)
        sample = next(iter(lot.samples.all()), None)
        photo = sample.best_photo if sample else None
        statuses = {p.status for p in sample.photos.all()} if sample else set()
        # "retake" only when the latest visit produced no usable photo at all
        photo_failed = SamplePhoto.Status.FAILED in statuses and SamplePhoto.Status.SCORED not in statuses
        photo_pending = SamplePhoto.Status.PENDING in statuses and SamplePhoto.Status.SCORED not in statuses
        photo_processing = SamplePhoto.Status.PROCESSING in statuses and SamplePhoto.Status.SCORED not in statuses
        photo_quality_low = bool(photo and not photo.quality_ok)
        days_to = pred.days_to_pack_by(today) if pred else None
        if days_to is None:
            urgency = ''
        elif days_to <= 7:
            urgency = 'red'
        elif days_to <= 14:
            urgency = 'amber'
        else:
            urgency = ''
        days_since_sample = (today - sample.sampled_on).days if sample else None
        sample_overdue = (days_since_sample if days_since_sample is not None else lot.days_in_storage) >= settings.sample_overdue_days
        if pred and pred.decay_flag:
            action = DECAY_RISK
        elif days_to is not None and days_to < 0:
            action = PACK_OVERDUE
        elif days_to is not None and days_to <= 7:
            action = PACK_THIS_WEEK
        elif photo_failed or photo_quality_low:
            action = RETAKE_PHOTO
        elif sample_overdue:
            action = SAMPLE_DUE
        elif days_to is not None and days_to <= 14:
            action = PACK_SOON
        elif photo_pending or photo_processing:
            action = SCORING
        elif pred:
            action = MONITOR
        else:
            action = NEEDS_BASELINE
        rows.append({
            'lot': lot,
            'pred': pred,
            'sample': sample,
            'photo': photo,
            'photo_failed': photo_failed,
            'photo_pending': photo_pending,
            'photo_processing': photo_processing,
            'photo_quality_low': photo_quality_low,
            'days_to_pack_by': days_to,
            'overdue_days': -days_to if days_to is not None and days_to < 0 else None,
            'urgency': urgency,
            'days_since_sample': days_since_sample,
            'sample_overdue': sample_overdue,
            'action': action,
            'priority': action.label,
            'priority_code': action.code,
            'priority_tone': action.tone,
            'priority_rank': action.rank,
            'requires_decision': action.requires_decision,
        })
    rows.sort(key=lambda r: (
        r['priority_rank'],
        r['pred'].pack_by_date if r['pred'] and r['pred'].pack_by_date else date.max,
        -r['lot'].days_in_storage,
    ))
    return rows


def capacity_projection(rows, plant, today, weeks=8):
    """Bucket known remaining bins by model pack-by week for planning."""
    week_zero = today - timedelta(days=today.weekday())
    capacity = plant.weekly_pack_capacity_bins if plant else None
    buckets = []
    for offset in range(weeks):
        start = week_zero + timedelta(days=7 * offset)
        end = start + timedelta(days=6)
        bucket_rows = []
        for row in rows:
            pack_by = row['pred'].pack_by_date if row['pred'] else None
            if not pack_by:
                continue
            if offset == 0:
                include = pack_by <= end
            else:
                include = start <= pack_by <= end
            if include:
                bucket_rows.append(row)
        known_bins = sum(
            (row['lot'].bins_remaining for row in bucket_rows if row['lot'].bins_remaining is not None),
            Decimal('0'),
        )
        unknown_bins = sum(1 for row in bucket_rows if row['lot'].bins_remaining is None)
        buckets.append({
            'start': start,
            'end': end,
            'lots': len(bucket_rows),
            'known_bins': known_bins,
            'unknown_bins': unknown_bins,
            'capacity': capacity,
            'over_capacity': capacity is not None and known_bins > capacity,
        })
    return buckets
