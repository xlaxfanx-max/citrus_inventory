"""Receiving import: creates or updates lots from the Famous receiving export.

Columns: plant_code, lot_no, grower_no, grower_name, block, variety,
         receive_date (YYYY-MM-DD), receiving_color (DG|LG|S|Y), bins_received,
         room, plus optional harvest_date, intake_cci_mean and intake_cci_std

Idempotent on (plant_code, lot_no): re-uploading the same file changes
nothing; an updated file updates the descriptive fields. A packed or dumped
lot never comes back to in_storage through this import. A changed room
records a LotRoomMove dated receive_date (Famous doesn't tell us when the
move happened; the room-moves file does).

Built for the 2,000-row acceptance test: all lookups are done in a handful
of queries, then one bulk_create and one bulk_update.
"""

from django.db import transaction
from django.db.models import Q

from ..models import Grower, Lot, LotRoomMove, Plant, Room
from .base import RowError, parse_color, parse_date, parse_int, require
from .base import parse_decimal

COLUMNS = [
    'plant_code', 'lot_no', 'grower_no', 'grower_name', 'block', 'variety',
    'receive_date', 'receiving_color', 'bins_received', 'room',
    'harvest_date', 'intake_cci_mean', 'intake_cci_std',
]
REQUIRED_COLUMNS = [
    'plant_code', 'lot_no', 'grower_no', 'grower_name', 'block', 'variety',
    'receive_date', 'receiving_color', 'bins_received', 'room',
]

VARIETY_MAP = {'eureka': Lot.Variety.EUREKA, 'lisbon': Lot.Variety.LISBON}


def parse_row(row):
    variety_raw = row.get('variety', '').strip().lower()
    variety = VARIETY_MAP.get(variety_raw, Lot.Variety.OTHER if variety_raw else Lot.Variety.LISBON)
    receive_date = parse_date(row.get('receive_date'), 'receive_date')
    harvest_date = parse_date(row.get('harvest_date'), 'harvest_date') if row.get('harvest_date') else None
    if harvest_date and harvest_date > receive_date:
        raise RowError('harvest_date cannot be after receive_date')
    intake_cci_std = parse_decimal(row.get('intake_cci_std'), 'intake_cci_std', default=None)
    if intake_cci_std is not None and intake_cci_std < 0:
        raise RowError(f'intake_cci_std: negative value {intake_cci_std}')
    return {
        'plant_code': require(row, 'plant_code').upper(),
        'lot_no': require(row, 'lot_no'),
        'grower_no': require(row, 'grower_no'),
        'grower_name': row.get('grower_name', ''),
        'block': row.get('block', '')[:50],
        'variety': variety,
        'receive_date': receive_date,
        'receiving_color': parse_color(row.get('receiving_color'), default=None) if row.get('receiving_color') else None,
        'bins_received': parse_int(row.get('bins_received'), 'bins_received', default=0) or None,
        'room': row.get('room', '')[:50],
        'harvest_date': harvest_date,
        'intake_cci_mean': parse_decimal(row.get('intake_cci_mean'), 'intake_cci_mean', default=None),
        'intake_cci_std': intake_cci_std,
    }


@transaction.atomic
def run(rows, batch=None):
    errors = []
    parsed = []
    seen = {}
    for i, row in enumerate(rows, start=2):  # line 1 is the header
        try:
            data = parse_row(row)
        except RowError as e:
            errors.append({'row': i, 'error': str(e)})
            continue
        key = (data['plant_code'], data['lot_no'])
        if key in seen:
            errors.append({'row': i, 'error': f'duplicate of row {seen[key]} ({key[0]} {key[1]}); later row ignored'})
            continue
        seen[key] = i
        parsed.append((i, data))

    plants = {p.code: p for p in Plant.objects.all()}
    usable = []
    for i, data in parsed:
        if data['plant_code'] not in plants:
            errors.append({'row': i, 'error': f'unknown plant_code {data["plant_code"]!r}'})
        else:
            usable.append((i, data))
    if not usable:
        return 0, errors

    # Growers: create missing, refresh names we were given.
    grower_nos = {d['grower_no'] for _, d in usable}
    growers = {g.sunkist_grower_no: g for g in Grower.objects.filter(sunkist_grower_no__in=grower_nos)}
    new_growers = {}
    for _, d in usable:
        if d['grower_no'] not in growers and d['grower_no'] not in new_growers:
            new_growers[d['grower_no']] = Grower(sunkist_grower_no=d['grower_no'], name=d['grower_name'] or d['grower_no'])
    if new_growers:
        Grower.objects.bulk_create(new_growers.values())
        growers.update({g.sunkist_grower_no: g for g in Grower.objects.filter(sunkist_grower_no__in=new_growers)})
    renamed = []
    for _, d in usable:
        g = growers[d['grower_no']]
        if d['grower_name'] and g.name != d['grower_name']:
            g.name = d['grower_name']
            renamed.append(g)
    if renamed:
        Grower.objects.bulk_update(renamed, ['name'])

    # Rooms per plant.
    rooms = {(r.plant_id, r.name): r for r in Room.objects.filter(plant__in=plants.values())}
    new_rooms = {}
    for _, d in usable:
        if d['room']:
            key = (plants[d['plant_code']].id, d['room'])
            if key not in rooms and key not in new_rooms:
                new_rooms[key] = Room(plant=plants[d['plant_code']], name=d['room'])
    if new_rooms:
        Room.objects.bulk_create(new_rooms.values())
        rooms.update({(r.plant_id, r.name): r for r in Room.objects.filter(plant__in=plants.values())})

    # Existing lots.
    existing = {
        (l.plant_id, l.lot_no): l
        for l in Lot.objects.filter(plant__in=plants.values(), lot_no__in={d['lot_no'] for _, d in usable})
    }
    observed_ids = set(
        Lot.objects.filter(pk__in=[lot.pk for lot in existing.values()])
        .filter(Q(samples__isnull=False) | Q(predictions__isnull=False))
        .values_list('pk', flat=True)
        .distinct()
    )

    to_create, to_update, moves = [], [], []
    rejected = 0
    for row_no, d in usable:
        plant = plants[d['plant_code']]
        grower = growers[d['grower_no']]
        room = rooms.get((plant.id, d['room'])) if d['room'] else None
        lot = existing.get((plant.id, d['lot_no']))
        if lot is None:
            lot = Lot(
                plant=plant, lot_no=d['lot_no'], grower=grower, block=d['block'], variety=d['variety'],
                receive_date=d['receive_date'],
                receiving_color=d['receiving_color'] or Lot._meta.get_field('receiving_color').default,
                bins_received=d['bins_received'], current_room=room,
                harvest_date=d['harvest_date'], intake_cci_mean=d['intake_cci_mean'],
                intake_cci_std=d['intake_cci_std'],
            )
            to_create.append(lot)
            if room is not None:
                moves.append((lot, room, d['receive_date']))
        else:
            immutable_changes = []
            if room is not None and lot.current_room_id is not None and lot.current_room_id != room.id and lot.status == Lot.Status.IN_STORAGE:
                immutable_changes.append('Room differs from the recorded location; import the actual room move before re-importing receiving.')
            if lot.pk in observed_ids and lot.receive_date != d['receive_date']:
                immutable_changes.append(
                    f'receive_date is locked at {lot.receive_date} after sampling/prediction'
                )
            if (
                lot.pk in observed_ids
                and d['receiving_color']
                and lot.receiving_color != d['receiving_color']
            ):
                immutable_changes.append(
                    f'receiving_color is locked at {lot.receiving_color} after sampling/prediction'
                )
            if immutable_changes:
                errors.append({'row': row_no, 'error': '; '.join(immutable_changes)})
                rejected += 1
                continue
            changed = False
            for field, value in (
                ('grower', grower), ('block', d['block']), ('variety', d['variety']),
                ('receive_date', d['receive_date']), ('bins_received', d['bins_received']),
                ('harvest_date', d['harvest_date']), ('intake_cci_mean', d['intake_cci_mean']),
                ('intake_cci_std', d['intake_cci_std']),
            ):
                if getattr(lot, field) != value:
                    setattr(lot, field, value)
                    changed = True
            if d['receiving_color'] and lot.receiving_color != d['receiving_color']:
                lot.receiving_color = d['receiving_color']
                changed = True
            if room is not None and lot.current_room_id is None and lot.status == Lot.Status.IN_STORAGE:
                lot.current_room = room
                moves.append((lot, room, d['receive_date']))
                changed = True
            if changed:
                to_update.append(lot)

    if to_create:
        Lot.objects.bulk_create(to_create)
    if to_update:
        Lot.objects.bulk_update(
            to_update, [
                'grower', 'block', 'variety', 'receive_date', 'receiving_color',
                'bins_received', 'current_room', 'harvest_date', 'intake_cci_mean',
                'intake_cci_std',
            ], batch_size=40
        )
    if moves:
        # bulk_create above assigned pks on the new lots (SQLite/Postgres both return ids).
        # Every receiving-file move is dated receive_date, so a lot that returns to a
        # room it was in before would collide on (lot, room, moved_at); the existing
        # move already records that room, so the duplicate is simply skipped.
        LotRoomMove.objects.bulk_create(
            [LotRoomMove(lot=lot, room=room, moved_at=when) for lot, room, when in moves],
            ignore_conflicts=True,
        )
    return len(usable) - rejected, errors
