from functools import wraps

from flask import abort
from flask_login import current_user

from app.models import Role


def role_required(*allowed_roles):
    """Restrict a view to one or more roles.

    Usage: @role_required(Role.ADMIN) or @role_required(Role.ADMIN, Role.STAFF)
    Assumes @login_required is already applied (or applied together, order
    doesn't matter as long as both decorate the view).
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.role not in [r.value for r in allowed_roles]:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
