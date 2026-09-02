"""Room sensor observations used to reconstruct lot temperature/gas exposure.

Loggers produce a reading every 15 minutes, so a month for one room is about
2,900 rows and a season for a plant is tens of thousands. Rows are validated
in Python and written with one bulk upsert per batch of 500 rather than one
save per reading.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Plant, Room, RoomCondition
from .base import RowError, parse_datetime, parse_decimal, require

COLUMNS = [
    'plant_code', 'room', 'recorded_at', 'temperature_f',
    'relative_humidity_pct', 'ethylene_ppm', 'co2_pct', 'source',
]
REQUIRED_COLUMNS = ['plant_code', 'room', 'recorded_at', 'temperature_f']


def parse_row(row):
    values = {
        'relative_humidity_pct': parse_decimal(
            row.get('relative_humidity_pct'), 'relative_humidity_pct', default=None
        ),
        'ethylene_ppm': parse_decimal(row.get('ethylene_ppm'), 'ethylene_ppm', default=None),
        'co2_pct': parse_decimal(row.get('co2_pct'), 'co2_pct', default=None),
    }
    for field in ('relative_humidity_pct', 'co2_pct'):
        if values[field] is not None and not 0 <= values[field] <= 100:
            raise RowError(f'{field}: expected 0 to 100, got {values[field]}')
    if values['ethylene_ppm'] is not None and values['ethylene_ppm'] < 0:
        raise RowError(f'ethylene_ppm: negative value {values["ethylene_ppm"]}')
    return {
        'plant_code': require(row, 'plant_code').upper(),
        'room': require(row, 'room')[:50],
        'recorded_at': parse_datetime(row.get('recorded_at'), 'recorded_at'),
        'temperature_f': parse_decimal(require(row, 'temperature_f'), 'temperature_f'),
        'source': (row.get('source') or 'csv')[:80],
        **values,
    }


@transaction.atomic
def run(rows, batch=None):
    errors, parsed, seen = [], [], {}
    for row_number, row in enumerate(rows, start=2):
        try:
            data = parse_row(row)
        except RowError as exc:
            errors.append({'row': row_number, 'error': str(exc)})
            continue
        key = (data['plant_code'], data['room'], data['recorded_at'], data['source'])
        if key in seen:
            errors.append({'row': row_number, 'error': f'duplicate of row {seen[key]}; later row ignored'})
            continue
        seen[key] = row_number
        parsed.append((row_number, data))

    plants = {plant.code: plant for plant in Plant.objects.all()}
    rooms = {(room.plant_id, room.name): room for room in Room.objects.select_related('plant')}
    readings = []
    for row_number, data in parsed:
        plant = plants.get(data['plant_code'])
        if plant is None:
            errors.append({'row': row_number, 'error': f'unknown plant_code {data["plant_code"]!r}'})
            continue
        room = rooms.get((plant.id, data['room']))
        if room is None:
            errors.append({
                'row': row_number,
                'error': f'unknown room {data["room"]!r}; import receiving or room moves first',
            })
            continue
        reading = RoomCondition(
            room=room,
            recorded_at=data['recorded_at'],
            source=data['source'],
            temperature_f=data['temperature_f'],
            relative_humidity_pct=data['relative_humidity_pct'],
            ethylene_ppm=data['ethylene_ppm'],
            co2_pct=data['co2_pct'],
            source_batch=batch,
        )
        try:
            # Field-level validation only: the FK is already resolved and the
            # unique key is handled by the upsert below.
            reading.full_clean(
                exclude=['room', 'source_batch'], validate_unique=False, validate_constraints=False
            )
        except ValidationError as exc:
            errors.append({'row': row_number, 'error': '; '.join(exc.messages)})
            continue
        readings.append(reading)
    if readings:
        RoomCondition.objects.bulk_create(
            readings,
            batch_size=500,
            update_conflicts=True,
            unique_fields=['room', 'recorded_at', 'source'],
            update_fields=[
                'temperature_f', 'relative_humidity_pct', 'ethylene_ppm', 'co2_pct', 'source_batch',
            ],
        )
    return len(readings), errors
