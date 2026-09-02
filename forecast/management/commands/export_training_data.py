"""Export point-in-time features and future labels for offline model development."""

import csv
import io
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from forecast.training import TRAINING_COLUMNS, training_rows
from lots.models import Lot, Plant


class Command(BaseCommand):
    help = 'Export leakage-safe sample snapshots and future quality labels as CSV.'

    def add_arguments(self, parser):
        parser.add_argument('--plant', help='Limit to a plant code such as SLA1.')
        parser.add_argument('--output', help='Write to this file instead of stdout.')

    def handle(self, *args, **options):
        lots = Lot.objects.select_related('plant', 'grower', 'current_room').order_by(
            'plant__code', 'receive_date', 'lot_no'
        )
        if options['plant']:
            code = options['plant'].upper()
            if not Plant.objects.filter(code=code).exists():
                raise CommandError(f'Unknown plant code {code!r}.')
            lots = lots.filter(plant__code=code)

        target = None
        if options['output']:
            path = Path(options['output']).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            target = path.open('w', newline='', encoding='utf-8')
        try:
            stream = target or io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=TRAINING_COLUMNS, lineterminator='\n')
            writer.writeheader()
            count = 0
            for row in training_rows(lots):
                writer.writerow(row)
                count += 1
            if target is None:
                self.stdout.write(stream.getvalue(), ending='')
            else:
                self.stdout.write(f'Exported {count} point-in-time rows to {path}.')
        finally:
            if target is not None:
                target.close()
