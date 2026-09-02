"""Seed the three Saticoy plants and the model settings row. Safe to re-run.

    python manage.py seed_plants

City names are placeholders until Bird confirms which code is which site.
"""

from django.core.management.base import BaseCommand

from ...models import ModelSettings, Plant

PLANTS = [
    ('SLA1', 'Saticoy Lemon Association plant 1', ''),
    ('SLA3', 'Saticoy Lemon Association plant 3', ''),
    ('SLA4', 'Saticoy Lemon Association plant 4', ''),
]


class Command(BaseCommand):
    help = 'Create the three Saticoy plants (SLA1, SLA3, SLA4) and default model settings.'

    def handle(self, *args, **options):
        for code, name, city in PLANTS:
            plant, created = Plant.objects.get_or_create(code=code, defaults={'name': name, 'city': city})
            self.stdout.write(f'{plant}: {"created" if created else "exists"}')
        ModelSettings.get()
        self.stdout.write('Model settings row present.')
