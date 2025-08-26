from django.utils import timezone
from django.contrib import messages
from django.conf import settings

from users.models import TimeEntry
try:
    from manager2.models import TimeManger
except Exception:
    TimeManger = None


class AutoShiftStopMiddleware:
    """
    Останавливает смену при превышении лимита и показывает уведомление на всех страницах.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)

        try:
            if user and user.is_authenticated:
                limit_seconds = getattr(settings, 'TIME_TRACKER_SHIFT_MAX_SECONDS', 24 * 3600)

                # Проверяем активную смену пользователя
                active_entry = TimeEntry.objects.filter(
                    user=user,
                    timer_type='shift',
                    end_time__isnull=True
                ).first()

                if active_entry:
                    elapsed = (timezone.now() - active_entry.start_time).total_seconds()
                    if elapsed >= limit_seconds:
                        # Завершаем смену на границе лимита, чтобы избежать переплаты
                        active_entry.end_time = active_entry.start_time + timezone.timedelta(seconds=limit_seconds)
                        active_entry.save()

                        # Сохраняем отметку в сессии, чтобы не дублировать уведомление
                        request.session['last_auto_stop_timeentry_id'] = active_entry.id
                        messages.info(request, 'Смена автоматически завершена по истечении лимита времени.')

                else:
                    # Если активной смены нет, проверим, не было ли недавно авто-завершения без уведомления
                    last_id_notified = request.session.get('last_auto_stop_timeentry_id')
                    last_finished = TimeEntry.objects.filter(
                        user=user,
                        timer_type='shift',
                        end_time__isnull=False
                    ).order_by('-end_time').first()

                    if last_finished and last_finished.id != last_id_notified:
                        duration_seconds = int((last_finished.end_time - last_finished.start_time).total_seconds())
                        # Считаем авто-стопом, если длительность ровно лимит (с допуском в 2 сек)
                        if abs(duration_seconds - limit_seconds) <= 2:
                            request.session['last_auto_stop_timeentry_id'] = last_finished.id
                            messages.info(request, 'Смена автоматически завершена по истечении лимита времени.')

                # Аналогичная логика для менеджеров (TimeManger)
                if TimeManger is not None:
                    active_mgr_entry = TimeManger.objects.filter(
                        manager=user,
                        end_time__isnull=True
                    ).first()

                    if active_mgr_entry:
                        elapsed_mgr = (timezone.now() - active_mgr_entry.start_time).total_seconds()
                        manager_limit = getattr(settings, 'TIME_TRACKER_MANAGER_MAX_SECONDS', limit_seconds)
                        if elapsed_mgr >= manager_limit:
                            active_mgr_entry.end_time = active_mgr_entry.start_time + timezone.timedelta(seconds=manager_limit)
                            active_mgr_entry.save()
                            request.session['last_auto_stop_timemanager_id'] = active_mgr_entry.id
                            messages.info(request, 'Смена автоматически завершена по истечении лимита времени.')
                    else:
                        last_mgr_id_notified = request.session.get('last_auto_stop_timemanager_id')
                        last_mgr_finished = TimeManger.objects.filter(
                            manager=user,
                            end_time__isnull=False
                        ).order_by('-end_time').first() if TimeManger else None

                        if last_mgr_finished and last_mgr_finished.id != last_mgr_id_notified:
                            duration_mgr_seconds = int((last_mgr_finished.end_time - last_mgr_finished.start_time).total_seconds())
                            manager_limit = getattr(settings, 'TIME_TRACKER_MANAGER_MAX_SECONDS', limit_seconds)
                            if abs(duration_mgr_seconds - manager_limit) <= 2:
                                request.session['last_auto_stop_timemanager_id'] = last_mgr_finished.id
                                messages.info(request, 'Смена автоматически завершена по истечении лимита времени.')

        except Exception:
            # Не ломаем запросы из-за ошибок в уведомлениях
            pass

        response = self.get_response(request)
        return response


