"""Publish a new versioned packing plan for one or all plants without
sending the report (the Monday report publishes its own version):

    python manage.py publish_plan [--plant SLA1] [--date 2026-10-06]
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from lots.models import Plant

from ...models import PackPlan
from ...plans import publish_plan


class Command(BaseCommand):
    help = 'Freeze the current ranked packing plan as a new version per plant.'

    def add_arguments(self, parser):
        parser.add_argument('--plant', default='', help='Plant code; default all plants')
        parser.add_argument('--date', default='', help='YYYY-MM-DD plan date; default today')

    def handle(self, *args, **options):
        plants = Plant.objects.all()
        if options['plant']:
            plants = plants.filter(code=options['plant'].upper())
            if not plants.exists():
                raise CommandError(f'no plant {options["plant"]!r}')
        today = date.fromisoformat(options['date']) if options['date'] else timezone.localdate()
        for plant in plants:
            plan = publish_plan(plant, today=today, source=PackPlan.Source.COMMAND)
            n = sum(1 for r in plan.recommendations.all() if r.requires_decision)
            self.stdout.write(self.style.SUCCESS(f'{plant.code}: plan v{plan.version} published for {today}; {n} recommendation(s) need a decision.'))
