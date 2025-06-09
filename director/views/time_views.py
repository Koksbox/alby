from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, ExpressionWrapper, FloatField, Q
from django.utils import timezone
from datetime import datetime, timedelta
from users.models import CustomUser, TimeEntry
from manager2.models import TimeManger
import logging

logger = logging.getLogger('director')

@login_required
def time_report(request):
    """Отчет по рабочему времени сотрудников"""
    logger.info(f'Пользователь {request.user} запросил отчет по рабочему времени')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    post_user = request.GET.get('post_user')
    sort_by = request.GET.get('sort_by', 'desc')

    try:
        if start_date and end_date:
            # Преобразуем строки в aware datetime объекты
            start_date = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d'))
            end_date_plus_one = end_date + timedelta(days=1)
        else:
            start_date = None
            end_date_plus_one = None
    except ValueError:
        logger.error(f'Ошибка в формате даты: start_date={start_date}, end_date={end_date}')
        start_date = None
        end_date_plus_one = None

    users = CustomUser.objects.filter(is_active=True)

    if start_date and end_date_plus_one:
        try:
            users = users.annotate(
                total_hours=Sum(
                    ExpressionWrapper(
                        (F('timeentry__end_time') - F('timeentry__start_time')) / timedelta(hours=1),
                        output_field=FloatField()
                    ),
                    filter=Q(timeentry__start_time__gte=start_date,
                            timeentry__end_time__lt=end_date_plus_one)
                )
            )
            total_hours = TimeEntry.total_hours_users(start_date=start_date, end_date=end_date_plus_one)
            individual_hours = TimeEntry.total_hours_for_each_user(start_date=start_date, end_date=end_date_plus_one)
            logger.info(f'Отчет по рабочему времени успешно сформирован для периода {start_date.strftime("%Y-%m-%d")} - {end_date.strftime("%Y-%m-%d")}')
        except ValueError as e:
            logger.error(f'Ошибка при формировании отчета по рабочему времени: {str(e)}')
            total_hours = 0
            individual_hours = {}
    else:
        total_hours = None
        individual_hours = {}

    users = users.exclude(post_user='manager')

    if post_user:
        users = users.filter(post_user=post_user)

    if sort_by == 'asc':
        users = users.order_by('total_hours')
    elif sort_by == 'desc':
        users = users.order_by('-total_hours')

    context = {
        'users': users,
        'total_hours': total_hours,
        'individual_hours': individual_hours,
        'post_user_choices': CustomUser.USER_TYPE_CHOICES,
        'selected_post_user': post_user,
        'sort_by': sort_by,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
    }
    return render(request, 'director/time_report.html', context)

@login_required
def time_manager(request):
    """Отчет по рабочему времени менеджеров"""
    logger.info(f'Пользователь {request.user} запросил отчет по рабочему времени менеджеров')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    post_user = request.GET.get('post_user')
    sort_by = request.GET.get('sort_by', 'desc')

    try:
        if start_date and end_date:
            start_date = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d'))
            end_date_plus_one = end_date + timedelta(days=1)
        else:
            start_date = None
            end_date_plus_one = None
    except ValueError:
        logger.error(f'Ошибка в формате даты: start_date={start_date}, end_date={end_date}')
        start_date = None
        end_date_plus_one = None

    users = CustomUser.objects.filter(is_active=True, post_user='manager')

    if start_date and end_date_plus_one:
        try:
            users = users.annotate(
                total_hours=Sum(
                    ExpressionWrapper(
                        (F('timemanger_set__end_time') - F('timemanger_set__start_time')) / timedelta(hours=1),
                        output_field=FloatField()
                    ),
                    filter=Q(timemanger_set__start_time__gte=start_date,
                            timemanger_set__end_time__lt=end_date_plus_one)
                )
            )
            total_hours = TimeManger.total_hours_users(start_date=start_date, end_date=end_date_plus_one)
            individual_hours = TimeManger.total_hours_for_each_user(start_date=start_date, end_date=end_date_plus_one)
            logger.info(f'Отчет по рабочему времени менеджеров успешно сформирован для периода {start_date.strftime("%Y-%m-%d")} - {end_date.strftime("%Y-%m-%d")}')
        except ValueError as e:
            logger.error(f'Ошибка при формировании отчета по рабочему времени менеджеров: {str(e)}')
            total_hours = 0
            individual_hours = {}
    else:
        total_hours = None
        individual_hours = {}

    if post_user:
        users = users.filter(post_user=post_user)

    if sort_by == 'asc':
        users = users.order_by('total_hours')
    elif sort_by == 'desc':
        users = users.order_by('-total_hours')

    context = {
        'users': users,
        'total_hours': total_hours,
        'individual_hours': individual_hours,
        'post_user_choices': CustomUser.USER_TYPE_CHOICES,
        'selected_post_user': post_user,
        'sort_by': sort_by,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
    }
    return render(request, 'director/time_manager.html', context) 