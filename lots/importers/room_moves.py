"""Room moves import (optional): where lots went and when.

Columns: plant_code, lot_no, room, moved_at

The CSV column is `moved_at` because it accepts either a date or a full
timestamp; the model stores the date as `moved_on` and the timestamp, when
given, as `occurred_at`.

Rooms that don't exist yet are created on the plant. A move that already
exists (same lot, room, date) is a no-op. The lot's current_room follows
its most recent move.
"""

from django.db import transaction

from ..models import Lot, LotRoomMove, Plant, Room
from .base import RowError, parse_date, parse_datetime, require

COLUMNS = ['plant_code', 'lot_no', 'room', 'moved_at']
REQUIRED_COLUMNS = COLUMNS


def parse_row(row):
    raw_time = row.get('moved_at')
    try:
        day = parse_date(raw_time, 'moved_at')
        occurred_at = None
    except RowError:
        from django.utils import timezone
        occurred_at = parse_datetime(raw_time, 'moved_at')
        day = timezone.localtime(occurred_at).date()
    return {
        'plant_code': require(row, 'plant_code').upper(),
        'lot_no': require(row, 'lot_no'),
        'room': require(row, 'room')[:50],
        'moved_on': day,
        'occurred_at': occurred_at,
    }


@transaction.atomic
def run(rows, batch=None):
    errors, parsed = [], []
    for i, row in enumerate(rows, start=2):
        try:
            parsed.append((i, parse_row(row)))
        except RowError as e:
            errors.append({'row': i, 'error': str(e)})
    if not parsed:
        return 0, errors

    plants = {p.code: p for p in Plant.objects.all()}
    lots = {
        (l.plant.code, l.lot_no): l
        for l in Lot.objects.filter(lot_no__in={d['lot_no'] for _, d in parsed}).select_related('plant')
    }
    rooms = {(r.plant_id, r.name): r for r in Room.objects.all()}

    ok = 0
    latest = {}
    for i, d in parsed:
        plant = plants.get(d['plant_code'])
        if plant is None:
            errors.append({'row': i, 'error': f'unknown plant_code {d["plant_code"]!r}'})
            continue
        lot = lots.get((d['plant_code'], d['lot_no']))
        if lot is None:
            errors.append({'row': i, 'error': f'unknown lot {d["plant_code"]} {d["lot_no"]} (import receiving first)'})
            continue
        if d['moved_on'] < lot.receive_date:
            errors.append({'row': i, 'error': f'moved_at {d["moved_on"]} is before receive_date {lot.receive_date}'})
            continue
        if lot.packed_date and d['moved_on'] > lot.packed_date:
            errors.append({'row': i, 'error': f'moved_at {d["moved_on"]} is after final packout {lot.packed_date}'})
            continue
        room = rooms.get((plant.id, d['room']))
        if room is None:
            room = Room.objects.create(plant=plant, name=d['room'])
            rooms[(plant.id, d['room'])] = room
        LotRoomMove.objects.get_or_create(lot=lot, room=room, moved_on=d['moved_on'], occurred_at=d['occurred_at'])
        ok += 1
        prev = latest.get(lot.pk)
        if prev is None or d['moved_on'] >= prev[0]:
            latest[lot.pk] = (d['moved_on'], room, lot)

    for when, room, lot in latest.values():
        newest = max(lot.room_moves.select_related('room'), key=lambda move: (move.effective_at, move.pk), default=None)
        if newest and newest.room_id != lot.current_room_id:
            lot.current_room = newest.room
            lot.save(update_fields=['current_room'])
    return ok, errors
