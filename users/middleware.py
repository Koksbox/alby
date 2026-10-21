"""Keep timer state in the database authoritative across tabs and devices."""

from django.contrib import messages
from django.utils import timezone

from manager2.models import TimeManger
from users.models import TimeEntry
from users.timers import expire_employee_shifts, expire_manager_shifts, shift_limit


class AutoShiftStopMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            expired = expire_employee_shifts(user)
            expired_managers = expire_manager_shifts(user)
            request.timer_shift_max_seconds = shift_limit()
            request.timer_manager_max_seconds = shift_limit(manager=True)
            request.session['timer_shift_started'] = TimeEntry.objects.filter(
                user=user, timer_type='shift', end_time__isnull=True,
            ).exists()
            manager_entry = TimeManger.objects.filter(manager=user, end_time__isnull=True).first()
            request.session['timer_started'] = manager_entry is not None
            request.manager_shift_id = manager_entry.pk if manager_entry else ''
            for entries, key in (
                (expired, 'last_auto_stop_timeentry_id'),
                (expired_managers, 'last_auto_stop_timemanager_id'),
            ):
                if entries and request.session.get(key) != entries[-1]:
                    request.session[key] = entries[-1]
                    messages.info(request, 'Смена автоматически завершена по истечении лимита времени.')
        return self.get_response(request)


class LastActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            if not request.user.last_activity or (now - request.user.last_activity).total_seconds() > 30:
                request.user.last_activity = now
                request.user.save(update_fields=['last_activity'])
        return self.get_response(request)
