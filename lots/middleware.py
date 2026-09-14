"""Language defaults for the plant floor.

Django's LocaleMiddleware honours the language cookie set by the toggle in
the header. When a foreman has never chosen a language, this middleware
activates the plant-floor default (Spanish, see FOREMAN_DEFAULT_LANGUAGE)
instead of the site default. GMs and admins keep English unless they choose
otherwise. Runs after AuthenticationMiddleware and LocaleMiddleware.
"""

from django.conf import settings
from django.utils import translation

from .roles import is_foreman, is_gm


class ForemanLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        default = getattr(settings, 'FOREMAN_DEFAULT_LANGUAGE', '')
        user = getattr(request, 'user', None)
        chosen = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if (
            default
            and not chosen
            and user is not None
            and user.is_authenticated
            and is_foreman(user)
            and not is_gm(user)
        ):
            translation.activate(default)
            request.LANGUAGE_CODE = translation.get_language()
        response = self.get_response(request)
        return response
