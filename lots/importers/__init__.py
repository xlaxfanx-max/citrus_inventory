"""Registry of CSV importers keyed by ImportBatch.Kind."""

from ..models import ImportBatch
from . import conditions, packout, receiving, room_moves, treatments
from .base import read_csv, template_csv

IMPORTERS = {
    ImportBatch.Kind.RECEIVING: receiving,
    ImportBatch.Kind.PACKOUT: packout,
    ImportBatch.Kind.ROOM_MOVES: room_moves,
    ImportBatch.Kind.CONDITIONS: conditions,
    ImportBatch.Kind.TREATMENTS: treatments,
}


def run_import(kind, file_obj, user=None, original_name='', plant_scope=None):
    """Parse the file, run the importer, record an ImportBatch. Returns the
    batch. Never raises for row problems; a completely unreadable file is
    recorded as a batch with one error and zero rows."""
    module = IMPORTERS[kind]
    batch = ImportBatch(
        kind=kind,
        uploaded_by=user,
        plant_scope=plant_scope,
        original_name=original_name or getattr(file_obj, 'name', ''),
    )
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    try:
        rows = read_csv(file_obj, required_columns=getattr(module, 'REQUIRED_COLUMNS', module.COLUMNS))
    except Exception as e:  # noqa: BLE001 - anything wrong with the file itself
        batch.rows_failed = 1
        batch.error_report = [{'row': 0, 'error': f'could not read file: {e}'}]
        batch.save()
        return batch
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
        try:
            batch.file.save(batch.original_name or 'upload.csv', file_obj, save=False)
        except Exception:  # noqa: BLE001 - storing the raw file is nice-to-have
            pass
    batch.save()
    if plant_scope is not None:
        foreign = [
            {'row': row_number, 'error': f'plant_code is outside your assigned plant {plant_scope.code}'}
            for row_number, row in enumerate(rows, start=2)
            if row.get('plant_code', '').strip().upper() not in {'', plant_scope.code}
        ]
        if foreign:
            batch.rows_failed = len(foreign)
            batch.error_report = foreign
            batch.save(update_fields=['rows_failed', 'error_report'])
            return batch
    try:
        ok, errors = module.run(rows, batch=batch)
    except Exception as e:  # noqa: BLE001 - preserve a failed audit row instead of returning a 500
        batch.rows_ok = 0
        batch.rows_failed = 1
        batch.error_report = [{'row': 0, 'error': f'import failed before completion: {e}'}]
        batch.save(update_fields=['rows_ok', 'rows_failed', 'error_report'])
        return batch
    batch.rows_ok = ok
    batch.rows_failed = len(errors)
    batch.error_report = errors
    batch.save(update_fields=['rows_ok', 'rows_failed', 'error_report'])
    return batch


def blank_template(kind):
    return template_csv(IMPORTERS[kind].COLUMNS)
