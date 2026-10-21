"""Shared POSIX locks: both web and worker must mount the same staging volume."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import fcntl

from django.conf import settings


@contextmanager
def backup_lock(name='worker.lock', blocking=True):
    root = Path(settings.BACKUP_STAGING_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / name
    if path.is_symlink():
        raise RuntimeError('Backup lock cannot be a symbolic link.')
    with path.open('a+b') as handle:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        fcntl.flock(handle.fileno(), flags)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def media_write_lock():
    return backup_lock('media.lock')


def media_write_view(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        # Several legacy deletion handlers also mutate on GET. Root wraps
        # only mutation-capable handlers; locking their GET is intentional.
        with media_write_lock():
            return view(request, *args, **kwargs)
    return wrapped
