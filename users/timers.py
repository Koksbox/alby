"""Shared, idempotent timer operations for the web and legacy API endpoints."""

from datetime import timedelta
from functools import wraps
import time

from django.conf import settings
from django.db import connection, OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from users.models import CustomUser, TimeEntry


def _retry_sqlite_lock(function):
    @wraps(function)
    def run(*args, **kwargs):
        for attempt in range(6):
            try:
                return function(*args, **kwargs)
            except OperationalError as exc:
                if connection.vendor != 'sqlite' or 'locked' not in str(exc).lower() or attempt == 5:
                    raise
                # Retry the entire transaction, never just a partially executed
                # read/create. In-memory shared SQLite returns SQLITE_LOCKED
                # immediately instead of honoring its normal busy timeout.
                time.sleep(0.025 * (2 ** attempt))
    return run


def shift_limit(manager=False):
    name = 'TIME_TRACKER_MANAGER_MAX_SECONDS' if manager else 'TIME_TRACKER_SHIFT_MAX_SECONDS'
    return int(getattr(settings, name, 24 * 3600))


def _lock_user(user):
    # This must be the first statement in the transaction. An UPDATE also
    # serializes writers on SQLite, where SELECT FOR UPDATE has no effect.
    CustomUser.objects.filter(pk=user.pk).update(last_activity=F('last_activity'))
    return CustomUser.objects.get(pk=user.pk)


def _expire(queryset, manager=False, now=None):
    now = now or timezone.now()
    limit = timedelta(seconds=shift_limit(manager))
    expired = []
    for entry in queryset.filter(end_time__isnull=True, start_time__lte=now - limit):
        end = entry.start_time + limit
        if queryset.model.objects.filter(pk=entry.pk, end_time__isnull=True).update(end_time=end):
            expired.append(entry.pk)
    return expired


def expire_employee_shifts(user=None, now=None):
    entries = TimeEntry.objects.filter(timer_type='shift')
    if user is not None:
        entries = entries.filter(user=user)
    return _expire(entries, now=now)


def expire_manager_shifts(user=None, now=None):
    from manager2.models import TimeManger

    entries = TimeManger.objects.all()
    if user is not None:
        entries = entries.filter(manager=user)
    return _expire(entries, manager=True, now=now)


def _shift_queryset(user, manager):
    if manager:
        from manager2.models import TimeManger

        return TimeManger.objects.filter(manager=user)
    return TimeEntry.objects.filter(user=user, timer_type='shift')


@_retry_sqlite_lock
def change_shift(user, action, manager=False, expected_entry_id=None):
    """Return (entry, changed); start/stop are safe to repeat.

    `expected_entry_id` prevents an old browser tab from stopping a newer shift.
    The legacy toggle action remains supported, but forms send explicit actions.
    """
    if action not in ('start', 'stop', 'toggle'):
        raise ValueError('Unknown timer action')
    with transaction.atomic():
        user = _lock_user(user)
        now = timezone.now()
        entries = _shift_queryset(user, manager)
        _expire(entries, manager=manager, now=now)
        active = entries.filter(end_time__isnull=True).order_by('start_time', 'pk').first()
        if action == 'toggle':
            action = 'stop' if active else 'start'
        if action == 'start':
            if active:
                return active, False
            values = {'start_time': now, 'hourly_rate': user.stavka()}
            values.update({'manager': user} if manager else {'user': user, 'timer_type': 'shift'})
            return entries.model.objects.create(**values), True
        if not active:
            return None, False
        if expected_entry_id not in (None, '') and str(active.pk) != str(expected_entry_id):
            return active, False
        end = max(active.start_time, min(now, active.start_time + timedelta(seconds=shift_limit(manager))))
        entries.filter(pk=active.pk, end_time__isnull=True).update(end_time=end)
        active.end_time = end
        return active, True


@_retry_sqlite_lock
def change_task_timer(user, task, action):
    if action not in ('start', 'stop'):
        raise ValueError('Unknown task timer action')
    with transaction.atomic():
        user = _lock_user(user)
        entries = TimeEntry.objects.filter(user=user, task=task, timer_type='task')
        active = entries.filter(end_time__isnull=True).first()
        if action == 'start':
            if active:
                return active, False
            return TimeEntry.objects.create(
                user=user, task=task, timer_type='task', start_time=timezone.now(), hourly_rate=0,
            ), True
        if active:
            active.end_time = max(active.start_time, timezone.now())
            active.save(update_fields=['end_time'])
            return active, True
        return None, False


def sync_task_session(request, task=None):
    entries = TimeEntry.objects.filter(user=request.user, timer_type='task', end_time__isnull=True)
    if task is not None:
        entries = entries.filter(task=task)
    entry = entries.order_by('start_time', 'pk').first()
    request.session['timer_running'] = entry is not None
    if entry:
        request.session['start_time'] = entry.start_time.isoformat()
    else:
        request.session.pop('start_time', None)
    return entry


def shift_payload(user, manager=False):
    entry = _shift_queryset(user, manager).filter(end_time__isnull=True).first()
    return {
        'active': entry is not None,
        'entry_id': entry.pk if entry else None,
        'elapsed_time': max(0, (timezone.now() - entry.start_time).total_seconds()) if entry else 0,
        'hourly_rate': (entry.hourly_rate if entry.hourly_rate is not None else user.stavka()) if entry else user.stavka(),
        'max_seconds': shift_limit(manager),
    }
