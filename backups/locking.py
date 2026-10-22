"""Shared file locks: both web and worker must mount the same staging volume.

POSIX uses fcntl.flock; Windows uses msvcrt.locking for local test/dev runs.
"""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import sys

from django.conf import settings

if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl


@contextmanager
def backup_lock(name='worker.lock', blocking=True):
    root = Path(settings.BACKUP_STAGING_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / name
    if path.is_symlink():
        raise RuntimeError('Backup lock cannot be a symbolic link.')
    with path.open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'\0')
            handle.flush()
        handle.seek(0)
        if sys.platform == 'win32':
            flag = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            msvcrt.locking(handle.fileno(), flag, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
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
