from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, 'profile', None)
            if profile is None or profile.role not in roles:
                if not request.user.is_superuser:
                    raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator

