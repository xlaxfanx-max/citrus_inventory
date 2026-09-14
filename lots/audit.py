"""Who is making the current change.

Model code cannot see the request, so the acting user is carried in a
context variable set by AuditUserMiddleware for web requests. Management
commands and importers may set it explicitly with `acting_as`.
"""

from contextlib import contextmanager
from contextvars import ContextVar

_current_user = ContextVar('current_user', default=None)
_current_source = ContextVar('current_source', default='')


def current_user():
    user = _current_user.get()
    return user if user is not None and getattr(user, 'is_authenticated', False) else None


def current_source():
    return _current_source.get()


@contextmanager
def acting_as(user=None, source=''):
    """Attribute changes made inside the block to `user` and `source`
    (for example 'import:receiving' or 'command:seed_demo')."""
    token_user = _current_user.set(user)
    token_source = _current_source.set(source)
    try:
        yield
    finally:
        _current_user.reset(token_user)
        _current_source.reset(token_source)


class AuditUserMiddleware:
    """Expose request.user to model-level change logging. Runs after
    AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with acting_as(getattr(request, 'user', None), f'web:{request.path}'):
            return self.get_response(request)
