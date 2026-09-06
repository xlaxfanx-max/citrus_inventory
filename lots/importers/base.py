"""Shared plumbing for the CSV importers.

Each importer exposes COLUMNS (the template header) and
`run(rows, batch=None) -> (rows_ok, errors)` where errors is a list of
{"row": <1-based line number in the file>, "error": "..."} dicts. Row
problems never abort an import: the good rows land, the bad ones are
reported.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from ..models import Color
from django.utils import timezone


class RowError(Exception):
    """A row that cannot be used. Message goes to the error report."""


def _norm_key(key):
    return str(key or '').strip().lower().lstrip('﻿').replace(' ', '_')


def read_csv(file_obj, required_columns=None):
    """Read an uploaded CSV (bytes or text file object) into a list of dicts
    keyed by lowercased, underscored header names. Values are stripped
    strings. A UTF-8 BOM from Excel is tolerated."""
    raw = file_obj.read()
    if isinstance(raw, bytes):
        text = raw.decode('utf-8-sig', errors='replace')
    else:
        text = raw.lstrip('﻿')
    reader = csv.DictReader(io.StringIO(text))
    headers = {_norm_key(h) for h in (reader.fieldnames or []) if h is not None}
    if not headers:
        raise ValueError('CSV has no header row')
    missing = [c for c in (required_columns or []) if _norm_key(c) not in headers]
    if missing:
        raise ValueError(f'CSV is missing required column(s): {", ".join(missing)}')
    rows = []
    for row in reader:
        clean = {_norm_key(k): (v or '').strip() for k, v in row.items() if k is not None}
        if any(clean.values()):
            rows.append(clean)
    return rows


def template_csv(columns):
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerow(columns)
    return buf.getvalue()


def require(row, key):
    val = row.get(key, '')
    if not val:
        raise RowError(f'missing {key}')
    return val


def parse_date(value, field):
    value = (value or '').strip()
    if not value:
        raise RowError(f'missing {field}')
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%Y/%m/%d'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise RowError(f'{field}: unrecognized date {value!r} (use YYYY-MM-DD)')


def parse_datetime(value, field):
    """Parse an ISO timestamp, treating a missing offset as the plant's local timezone."""
    value = (value or '').strip()
    if not value:
        raise RowError(f'missing {field}')
    normalized = value[:-1] + '+00:00' if value.endswith(('Z', 'z')) else value
    parsed = None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ('%Y-%m-%d %H:%M', '%m/%d/%Y %H:%M', '%m/%d/%Y %I:%M %p'):
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise RowError(
            f'{field}: unrecognized timestamp {value!r} '
            '(use YYYY-MM-DD HH:MM or ISO 8601 with an offset)'
        )
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def parse_int(value, field, default=None):
    value = (value or '').strip().replace(',', '')
    if not value:
        if default is not None:
            return default
        raise RowError(f'missing {field}')
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise RowError(f'{field}: not a number {value!r}')
    if not number.is_finite() or number != number.to_integral_value():
        raise RowError(f'{field}: expected a finite whole number, got {value!r}')
    n = int(number)
    if n < 0:
        raise RowError(f'{field}: negative value {n}')
    return n


def parse_decimal(value, field, default=None):
    value = (value or '').strip().replace(',', '')
    if not value:
        return default
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise RowError(f'{field}: not a number {value!r}')
    if not number.is_finite():
        raise RowError(f'{field}: not a finite number {value!r}')
    return number


def parse_bool(value, field, default=None):
    text = (value or '').strip().lower()
    if not text:
        return default
    if text in {'1', 'true', 'yes', 'y', 'final'}:
        return True
    if text in {'0', 'false', 'no', 'n', 'partial'}:
        return False
    raise RowError(f'{field}: expected yes/no, true/false, final/partial or 1/0, got {value!r}')


COLOR_ALIASES = {
    'dg': Color.DARK_GREEN, 'dark green': Color.DARK_GREEN, 'darkgreen': Color.DARK_GREEN, 'dark_green': Color.DARK_GREEN,
    'lg': Color.LIGHT_GREEN, 'light green': Color.LIGHT_GREEN, 'lightgreen': Color.LIGHT_GREEN, 'light_green': Color.LIGHT_GREEN, 'g': Color.LIGHT_GREEN, 'green': Color.LIGHT_GREEN,
    's': Color.SILVER, 'sl': Color.SILVER, 'silver': Color.SILVER, 'sg': Color.SILVER, 'silver green': Color.SILVER,
    'y': Color.YELLOW, 'yl': Color.YELLOW, 'yellow': Color.YELLOW,
}


def parse_color(value, field='receiving_color', default=None):
    text = (value or '').strip().lower()
    if not text:
        if default is not None:
            return default
        raise RowError(f'missing {field}')
    try:
        return COLOR_ALIASES[text]
    except KeyError:
        raise RowError(f'{field}: expected DG, LG, S or Y, got {value!r}')


def row_errors(parsed_errors):
    """Format helper so every importer reports the same shape."""
    return [{'row': i, 'error': str(e)} for i, e in parsed_errors]
