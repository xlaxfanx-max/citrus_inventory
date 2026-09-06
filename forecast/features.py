"""Leakage-safe feature snapshots for prediction and offline calibration."""

from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from lots.models import RoomCondition

MEASURES = ('temperature_f', 'relative_humidity_pct', 'ethylene_ppm', 'co2_pct')


def _aware_start(day):
    value = datetime.combine(day, time.min)
    return timezone.make_aware(value, timezone.get_current_timezone())


def room_exposure_intervals(lot, as_of):
    """Return known room intervals through as_of, excluding later moves."""
    end_day = min(as_of, lot.packed_date) if lot.packed_date else as_of
    if end_day < lot.receive_date:
        return []
    moves = sorted(
        lot.room_moves.filter(moved_at__lte=end_day)
        .select_related('room'), key=lambda move: (move.effective_at, move.pk)
    )
    intervals = []
    active_room = None
    active_start = _aware_start(lot.receive_date)
    for move in moves:
        move_day = max(move.effective_at, _aware_start(lot.receive_date))
        if active_room is not None and move_day > active_start:
            intervals.append((active_room, active_start, move_day))
        active_room = move.room
        active_start = move_day
    if active_room is not None:
        intervals.append((active_room, active_start, _aware_start(end_day + timedelta(days=1))))
    # A current room alone cannot establish where a lot spent its history.
    return intervals


def environment_features(lot, as_of):
    """Exposure summary through as_of. One aggregate query per room interval;
    raw readings (up to 96 a day per room) never leave the database."""
    intervals = room_exposure_intervals(lot, as_of)
    interval_rows = []
    reading_count = observed_days = 0
    parts = {field: [] for field in MEASURES}
    aggregates = {'n': Count('id'), 'days': Count(TruncDate('recorded_at'), distinct=True)}
    coverage_filter = Q(pk__in=[])
    for field in MEASURES:
        aggregates.update({
            f'{field}__mean': Avg(field), f'{field}__min': Min(field),
            f'{field}__max': Max(field), f'{field}__n': Count(field),
        })
    for room, start_day, end_day in intervals:
        interval_filter = Q(
            room=room,
            recorded_at__gte=start_day,
            recorded_at__lt=end_day,
        )
        coverage_filter |= interval_filter
        agg = RoomCondition.objects.filter(interval_filter).aggregate(**aggregates)
        reading_count += agg['n']
        for field in MEASURES:
            if agg[f'{field}__n']:
                parts[field].append((agg[f'{field}__mean'], agg[f'{field}__min'], agg[f'{field}__max'], agg[f'{field}__n']))
        interval_rows.append({
            'room_id': room.pk,
            'room': room.name,
            'start': start_day.isoformat(),
            'end_exclusive': end_day.isoformat(),
            'days': (end_day - start_day).total_seconds() / 86400,
            'reading_count': agg['n'],
        })
    exposure_days = sum(row['days'] for row in interval_rows)
    # Different rooms can now contribute readings on the same day. Count
    # calendar-day coverage once across all intervals, without fetching raw data.
    observed_days = RoomCondition.objects.filter(coverage_filter).aggregate(days=Count(TruncDate('recorded_at'), distinct=True))['days'] if intervals else 0
    calendar_days = (min(as_of, lot.packed_date) if lot.packed_date else as_of) - lot.receive_date
    calendar_days = max(0, calendar_days.days + 1)
    return {
        'intervals': interval_rows,
        'exposure_days': exposure_days,
        'reading_count': reading_count,
        'observed_days': observed_days,
        'day_coverage_pct': round(100 * observed_days / calendar_days, 1) if calendar_days else 0.0,
        'date_only_move_count': lot.room_moves.filter(moved_at__lte=as_of, occurred_at__isnull=True).count(),
        **{field: _combine(parts[field]) for field in MEASURES},
    }


def _combine(parts):
    """Merge per-interval (mean, min, max, n) tuples into one pooled summary."""
    if not parts:
        return None
    n = sum(p[3] for p in parts)
    return {
        'mean': round(sum(float(p[0]) * p[3] for p in parts) / n, 3),
        'min': round(min(float(p[1]) for p in parts), 3),
        'max': round(max(float(p[2]) for p in parts), 3),
        'n': n,
    }


def treatment_features(lot, as_of):
    end = _aware_start(as_of + timedelta(days=1))
    events = list(lot.treatments.filter(applied_at__lt=end).order_by('applied_at', 'id'))
    return [{
        'id': event.pk,
        'applied_at': event.applied_at.isoformat(),
        'type': event.treatment_type,
        'product': event.product,
        'concentration': float(event.concentration) if event.concentration is not None else None,
        'concentration_unit': event.concentration_unit,
        'duration_hours': float(event.duration_hours) if event.duration_hours is not None else None,
    } for event in events]


def features_for_lot(lot, as_of):
    """All model candidates observable by the end of as_of."""
    return {
        'plant_code': lot.plant.code,
        'variety': lot.variety,
        'grower_id': lot.grower_id,
        'block': lot.block,
        'harvest_date': lot.harvest_date.isoformat() if lot.harvest_date else None,
        'harvest_to_receive_days': (
            (lot.receive_date - lot.harvest_date).days if lot.harvest_date else None
        ),
        'intake_cci_mean': lot.intake_cci_mean,
        'intake_cci_std': lot.intake_cci_std,
        'environment': environment_features(lot, as_of),
        'treatments': treatment_features(lot, as_of),
    }
