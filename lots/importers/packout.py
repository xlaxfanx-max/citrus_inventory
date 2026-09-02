"""Packout import: what actually packed out of each lot.

Columns: plant_code, lot_no, packed_date, cartons_fancy, cartons_choice,
         cartons_standard, cartons_products

One Packout row per (lot, packed_date); re-uploading updates in place.
Importing a packout row sets Lot.status = packed and Lot.packed_date to the
latest pack date seen. Predictions are not touched: the Accuracy page
compares the last prediction *before* packed_date with what happened.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Lot, Packout, Plant
from .base import (
    RowError,
    parse_bool,
    parse_color,
    parse_date,
    parse_decimal,
    parse_int,
    require,
)

REQUIRED_COLUMNS = [
    'plant_code', 'lot_no', 'packed_date',
    'cartons_fancy', 'cartons_choice', 'cartons_standard', 'cartons_products',
]
COLUMNS = REQUIRED_COLUMNS + [
    'bins_packed', 'is_final', 'packout_color', 'decay_pct', 'downgrade_reason',
    'soft_pct', 'shrivel_pct', 'chilling_injury_pct', 'meets_spec',
]


def parse_row(row):
    bins_packed = parse_decimal(row.get('bins_packed'), 'bins_packed', default=None)
    decay_pct = parse_decimal(row.get('decay_pct'), 'decay_pct', default=None)
    if bins_packed is not None and bins_packed < 0:
        raise RowError(f'bins_packed: negative value {bins_packed}')
    quality_percentages = {
        field: parse_decimal(row.get(field), field, default=None)
        for field in ('soft_pct', 'shrivel_pct', 'chilling_injury_pct')
    }
    quality_percentages['decay_pct'] = decay_pct
    for field, value in quality_percentages.items():
        if value is not None and not 0 <= value <= 100:
            raise RowError(f'{field}: expected 0 to 100, got {value}')
    return {
        'plant_code': require(row, 'plant_code').upper(),
        'lot_no': require(row, 'lot_no'),
        'packed_date': parse_date(row.get('packed_date'), 'packed_date'),
        'cartons_fancy': parse_int(row.get('cartons_fancy'), 'cartons_fancy', default=0),
        'cartons_choice': parse_int(row.get('cartons_choice'), 'cartons_choice', default=0),
        'cartons_standard': parse_int(row.get('cartons_standard'), 'cartons_standard', default=0),
        'cartons_products': parse_int(row.get('cartons_products'), 'cartons_products', default=0),
        'bins_packed': bins_packed,
        'is_final': parse_bool(row.get('is_final'), 'is_final', default=True),
        'packout_color': parse_color(row.get('packout_color'), field='packout_color') if row.get('packout_color') else '',
        'decay_pct': decay_pct,
        'soft_pct': quality_percentages['soft_pct'],
        'shrivel_pct': quality_percentages['shrivel_pct'],
        'chilling_injury_pct': quality_percentages['chilling_injury_pct'],
        'meets_spec': parse_bool(row.get('meets_spec'), 'meets_spec', default=None),
        'downgrade_reason': row.get('downgrade_reason', '')[:200],
    }


@transaction.atomic
def run(rows, batch=None):
    errors, parsed = [], []
    seen = {}
    for i, row in enumerate(rows, start=2):
        try:
            data = parse_row(row)
        except RowError as e:
            errors.append({'row': i, 'error': str(e)})
            continue
        key = (data['plant_code'], data['lot_no'], data['packed_date'])
        if key in seen:
            errors.append({'row': i, 'error': f'duplicate of row {seen[key]}; later row ignored'})
            continue
        seen[key] = i
        parsed.append((i, data))
    if not parsed:
        return 0, errors

    plants = {p.code: p for p in Plant.objects.all()}
    lots = {
        (l.plant.code, l.lot_no): l
        for l in Lot.objects.filter(lot_no__in={d['lot_no'] for _, d in parsed}).select_related('plant')
    }

    ok = 0
    touched = {}
    for i, d in parsed:
        if d['plant_code'] not in plants:
            errors.append({'row': i, 'error': f'unknown plant_code {d["plant_code"]!r}'})
            continue
        lot = lots.get((d['plant_code'], d['lot_no']))
        if lot is None:
            errors.append({'row': i, 'error': f'unknown lot {d["plant_code"]} {d["lot_no"]} (import receiving first)'})
            continue
        if d['cartons_fancy'] + d['cartons_choice'] + d['cartons_standard'] + d['cartons_products'] == 0:
            errors.append({'row': i, 'error': 'all carton counts are zero'})
            continue
        if d['packed_date'] < lot.receive_date:
            errors.append({'row': i, 'error': f'packed_date {d["packed_date"]} is before receive_date {lot.receive_date}'})
            continue
        try:
            Packout.objects.update_or_create(
                lot=lot,
                packed_date=d['packed_date'],
                defaults={
                    'cartons_fancy': d['cartons_fancy'],
                    'cartons_choice': d['cartons_choice'],
                    'cartons_standard': d['cartons_standard'],
                    'cartons_products': d['cartons_products'],
                    'bins_packed': d['bins_packed'],
                    'is_final': d['is_final'],
                    'packout_color': d['packout_color'],
                    'decay_pct': d['decay_pct'],
                    'soft_pct': d['soft_pct'],
                    'shrivel_pct': d['shrivel_pct'],
                    'chilling_injury_pct': d['chilling_injury_pct'],
                    'meets_spec': d['meets_spec'],
                    'downgrade_reason': d['downgrade_reason'],
                    'source_batch': batch,
                },
            )
        except ValidationError as exc:
            errors.append({'row': i, 'error': '; '.join(exc.messages)})
            continue
        ok += 1
        touched[lot.pk] = lot

    if touched:
        for lot in touched.values():
            final = lot.packouts.filter(is_final=True).order_by('-packed_date').first()
            if final is not None:
                lot.status = Lot.Status.PACKED
                lot.packed_date = final.packed_date
            elif lot.status == Lot.Status.PACKED:
                lot.status = Lot.Status.IN_STORAGE
                lot.packed_date = None
        Lot.objects.bulk_update(touched.values(), ['status', 'packed_date'])
    return ok, errors
