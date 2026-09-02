"""Rebuild predictions for every in-storage lot. Run nightly (photos that
score during the day also trigger a rebuild for their lot):

    python manage.py build_predictions [--plant SLA1] [--as-of 2026-10-06]
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from lots.models import Plant

from ...services import rebuild_all


class Command(BaseCommand):
    help = 'Rebuild the drift predictions for all in-storage lots.'

    def add_arguments(self, parser):
        parser.add_argument('--plant', default='', help='Plant code; default all plants')
        parser.add_argument('--as-of', default='', help='YYYY-MM-DD; default today')

    def handle(self, *args, **options):
        plant = None
        if options['plant']:
            try:
                plant = Plant.objects.get(code=options['plant'].upper())
            except Plant.DoesNotExist:
                raise CommandError(f'no plant {options["plant"]!r}')
        as_of = date.fromisoformat(options['as_of']) if options['as_of'] else None
        n = rebuild_all(plant=plant, as_of=as_of)
        self.stdout.write(self.style.SUCCESS(f'{n} predictions written as of {as_of or timezone.localdate()}.'))
