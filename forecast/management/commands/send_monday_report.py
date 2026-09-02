"""Send the Monday report for one or all plants. Schedule for 05:30 Pacific
every Monday (cron: `30 5 * * 1`, TZ=America/Los_Angeles):

    python manage.py send_monday_report [--plant SLA1] [--date 2026-10-06] [--dry-run]

--dry-run prints the text version instead of emailing.
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from lots.models import Plant

from ...report import build_report, render_report, send_report


class Command(BaseCommand):
    help = 'Email the Monday pack-list report per plant.'

    def add_arguments(self, parser):
        parser.add_argument('--plant', default='')
        parser.add_argument('--date', default='')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true', help='Send again even if this plant/date already succeeded.')

    def handle(self, *args, **options):
        plants = Plant.objects.all()
        if options['plant']:
            plants = plants.filter(code=options['plant'].upper())
            if not plants.exists():
                raise CommandError(f'no plant {options["plant"]!r}')
        today = date.fromisoformat(options['date']) if options['date'] else timezone.localdate()
        failed = []
        for plant in plants:
            if options['dry_run']:
                subject, _html, text = render_report(build_report(plant, today=today))
                self.stdout.write(f'--- {subject}\n{text}')
                continue
            try:
                n = send_report(plant, today=today, force=options['force'])
            except Exception as exc:  # keep sending the other plants, then exit non-zero
                failed.append(f'{plant.code}: {exc}')
                self.stderr.write(self.style.ERROR(f'{plant.code}: report failed: {exc}'))
                continue
            if n:
                if n == -1:
                    self.stdout.write(f'{plant.code}: already sent for {today}; skipped duplicate.')
                else:
                    self.stdout.write(self.style.SUCCESS(f'{plant.code}: sent to {n} recipient(s).'))
            else:
                self.stdout.write(self.style.WARNING(f'{plant.code}: no recipients configured, not sent.'))
        if failed:
            raise CommandError('; '.join(failed))
