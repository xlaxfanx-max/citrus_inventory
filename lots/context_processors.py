from .models import plant_for
from .roles import is_admin, is_foreman, is_gm


def roles(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        'is_foreman': is_foreman(user),
        'is_gm': is_gm(user),
        'is_admin': is_admin(user),
        'user_plant': plant_for(user),
    }
