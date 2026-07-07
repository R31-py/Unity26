from functools import wraps
from flask import abort
from flask_login import current_user

from app.models import RoleEnum


def login_required_active(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_active_account:
            abort(401)
        return f(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    """Lejon vetëm rolet e specifikuara. Superuser NUK anashkalon këtu me qëllim -
    superuser ka panelin e vet të veçantë dhe s'duhet të "shtiret" si admin/staf
    brenda rrjedhave normale të UI-t."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.is_superuser:
                abort(404)  # superuser nuk përdor panelet normale
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.is_superuser:
                abort(404)
            if not current_user.has_permission(permission):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def superuser_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        # E qëllimshme: përgjigje 404 (jo 403) nëse s'je superuser, që panelin
        # ta mos e dallojë as ekzistenca e tij nga jashtë.
        if not current_user.is_authenticated or not current_user.is_superuser:
            abort(404)
        return f(*args, **kwargs)
    return wrapped