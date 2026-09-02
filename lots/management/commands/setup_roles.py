"""Create the three auth groups (foreman, gm, admin) and give the admin group
Django-admin access to everything. Safe to re-run.

    python manage.py setup_roles
"""

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create the foreman, gm and admin groups.'

    def handle(self, *args, **options):
        for name in settings.ROLE_GROUPS:
            group, created = Group.objects.get_or_create(name=name)
            if name == 'admin':
                group.permissions.set(
                    Permission.objects.filter(
                        content_type__app_label__in=['lots', 'sampling', 'forecast', 'auth']
                    )
                )
            elif name == 'gm':
                group.permissions.set(
                    Permission.objects.filter(
                        content_type__app_label__in=['lots', 'sampling', 'forecast'],
                        codename__startswith='view_',
                    )
                )
            else:
                group.permissions.clear()
            self.stdout.write(f'{name}: {"created" if created else "exists"}')
        self.stdout.write(
            'Give application admins is_staff=True to use Django admin. '
            'GMs use the application screens with view-only model permissions. '
            'Pin every foreman to a plant via a UserProfile.'
        )
