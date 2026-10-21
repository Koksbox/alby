from django.core.exceptions import PermissionDenied
from functools import wraps

from users.role_utils import is_director


def backup_director_required(view):
    """An explicit backup permission supplements the existing director identity."""
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not is_director(request.user) or not request.user.has_perm('backups.manage_backups'):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return guarded
