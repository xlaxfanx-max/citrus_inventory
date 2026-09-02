"""Lot-level treatment events, including ethylene, coatings and fungicides."""

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Lot, LotTreatment, Plant
from .base import RowError, parse_datetime, parse_decimal, require

COLUMNS = [
    'plant_code', 'lot_no', 'applied_at', 'treatment_type', 'product',
    'concentration', 'concentration_unit', 'duration_hours', 'notes',
]
REQUIRED_COLUMNS = ['plant_code', 'lot_no', 'applied_at', 'treatment_type']

TYPE_ALIASES = {
    value.lower(): value for value, _ in LotTreatment.TreatmentType.choices
}
TYPE_ALIASES.update({
    '1-mcp': LotTreatment.TreatmentType.ONE_MCP,
    'mcp': LotTreatment.TreatmentType.ONE_MCP,
    'ga3': LotTreatment.TreatmentType.GA3,
    '2,4-d': LotTreatment.TreatmentType.TWO_FOUR_D,
    '2-4-d': LotTreatment.TreatmentType.TWO_FOUR_D,
    'coating': LotTreatment.TreatmentType.WAX,
})


def parse_row(row):
    raw_type = require(row, 'treatment_type').strip().lower()
    treatment_type = TYPE_ALIASES.get(raw_type)
    if treatment_type is None:
        allowed = ', '.join(value for value, _ in LotTreatment.TreatmentType.choices)
        raise RowError(f'treatment_type: expected one of {allowed}, got {raw_type!r}')
    concentration = parse_decimal(row.get('concentration'), 'concentration', default=None)
    duration = parse_decimal(row.get('duration_hours'), 'duration_hours', default=None)
    if concentration is not None and concentration < 0:
        raise RowError(f'concentration: negative value {concentration}')
    if duration is not None and duration < 0:
        raise RowError(f'duration_hours: negative value {duration}')
    return {
        'plant_code': require(row, 'plant_code').upper(),
        'lot_no': require(row, 'lot_no'),
        'applied_at': parse_datetime(row.get('applied_at'), 'applied_at'),
        'treatment_type': treatment_type,
        'product': row.get('product', '')[:100],
        'concentration': concentration,
        'concentration_unit': row.get('concentration_unit', '')[:20],
        'duration_hours': duration,
        'notes': row.get('notes', '')[:250],
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
        key = (
            data['plant_code'], data['lot_no'], data['applied_at'],
            data['treatment_type'], data['product'],
        )
        if key in seen:
            errors.append({'row': row_number, 'error': f'duplicate of row {seen[key]}; later row ignored'})
            continue
        seen[key] = row_number
        parsed.append((row_number, data))

    plants = {plant.code: plant for plant in Plant.objects.all()}
    lots = {
        (lot.plant.code, lot.lot_no): lot
        for lot in Lot.objects.filter(lot_no__in={data['lot_no'] for _, data in parsed})
        .select_related('plant')
    }
    ok = 0
    for row_number, data in parsed:
        if data['plant_code'] not in plants:
            errors.append({'row': row_number, 'error': f'unknown plant_code {data["plant_code"]!r}'})
            continue
        lot = lots.get((data['plant_code'], data['lot_no']))
        if lot is None:
            errors.append({
                'row': row_number,
                'error': f'unknown lot {data["plant_code"]} {data["lot_no"]} (import receiving first)',
            })
            continue
        defaults = {
            'concentration': data['concentration'],
            'concentration_unit': data['concentration_unit'],
            'duration_hours': data['duration_hours'],
            'notes': data['notes'],
            'source_batch': batch,
        }
        try:
            LotTreatment.objects.update_or_create(
                lot=lot,
                applied_at=data['applied_at'],
                treatment_type=data['treatment_type'],
                product=data['product'],
                defaults=defaults,
            )
        except ValidationError as exc:
            errors.append({'row': row_number, 'error': '; '.join(exc.messages)})
            continue
        ok += 1
    return ok, errors
