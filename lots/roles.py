"""Role checks for the three groups (foreman, gm, admin) and plant scoping.

Superusers pass every check. GM implies everything a foreman can do; admin
implies everything a GM can do.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Plant, plant_for

FOREMAN, GM, ADMIN = 'foreman', 'gm', 'admin'


def in_groups(user, *names):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=names).exists()


def is_admin(user):
    return in_groups(user, ADMIN)


def is_gm(user):
    return in_groups(user, GM, ADMIN)


def is_foreman(user):
    return in_groups(user, FOREMAN, GM, ADMIN)


def group_required(*names):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not in_groups(request.user, *names):
                raise PermissionDenied
            if not is_gm(request.user) and plant_for(request.user) is None:
                raise PermissionDenied('A plant assignment is required for this account.')
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def resolve_plant(request):
    """Which plant this request is about.

    A user pinned to a plant always gets that plant. All-plant users (GM or
    admin with no profile plant) pick via ?plant=CODE, remembered in the
    session, defaulting to the first plant. Returns (plant, switchable_plants)
    where switchable_plants is empty for pinned users.
    """
    pinned = plant_for(request.user)
    if pinned is not None:
        return pinned, []
    if not is_gm(request.user):
        # A foreman without a plant assignment must never fall through to
        # cross-plant access.
        raise PermissionDenied('A plant assignment is required for this account.')
    plants = list(Plant.objects.all())
    if not plants:
        return None, []
    code = request.GET.get('plant') or request.session.get('plant_code')
    plant = next((p for p in plants if p.code == code), plants[0])
    request.session['plant_code'] = plant.code
    return plant, plants
