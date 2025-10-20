from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Q, F, ExpressionWrapper, FloatField, IntegerField, OuterRef, Subquery, Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from users.models import CustomUser, TimeEntry, PrizeHistory
from manager2.models import Task, TaskReview, TimeManger
import logging

logger = logging.getLogger('director')

@login_required
def home_director(request):
    """Главная страница директора со статистикой"""
    logger.info(f'Пользователь {request.user} открыл главную страницу директора')
    
    total_users = CustomUser.objects.filter(is_active=True).count()
    active_users = CustomUser.objects.filter(is_active=True, post_user__in=['employee', 'manager', 'junior_manager', 'senior_manager']).count()
    completed_tasks = Task.objects.filter(completed=True).count()
    
    # Расчет среднего времени выполнения задачи
    task_times = []
    for task in Task.objects.filter(completed=True):
        if task.created_at and task.completed_at:
            time_diff = task.completed_at - task.created_at
            task_times.append(time_diff.total_seconds() / 3600)  # в часах
    
    avg_task_time = sum(task_times) / len(task_times) if task_times else 0
    
    # Расчет общей зарплаты
    total_salary = TimeEntry.total_salary_users_money_user()
    total_prizes = CustomUser.objects.aggregate(total=Sum('prize'))['total'] or 0
    
    logger.info(f'Статистика успешно сформирована: {total_users} пользователей, {active_users} активных, {completed_tasks} выполненных задач')
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'completed_tasks': completed_tasks,
        'avg_task_time': round(avg_task_time, 2),
        'total_salary': total_salary,
        'total_prizes': total_prizes,
    }
    return render(request, 'director/home_director.html', context)

@login_required
def director_user_statistic(request, user_id):
    """Статистика по конкретному пользователю"""
    user = get_object_or_404(CustomUser, id=user_id)
    logger.info(f'Пользователь {request.user} просматривает статистику сотрудника {user.full_name}')
    
    selected_month_str = request.GET.get('month')
    selected_month = timezone.now().date()

    if selected_month_str:
        try:
            selected_month = datetime.strptime(selected_month_str, '%Y-%m').date()
        except (ValueError, TypeError):
            logger.error(f'Некорректный формат месяца: {selected_month_str}')
            pass

    first_day_of_month = selected_month.replace(day=1)
    last_day_of_month = (selected_month.replace(month=selected_month.month + 1, day=1) 
                        if selected_month.month < 12 
                        else selected_month.replace(year=selected_month.year + 1, month=1, day=1))

    # Статистика по задачам
    completed_tasks = TaskReview.objects.filter(
        user=user,
        task__completed=True,
        task__created_at__gte=first_day_of_month,
        task__created_at__lt=last_day_of_month
    ).count()

    # Статистика по фотографиям
    worked_photos = Task.objects.filter(
        assigned_users=user,
        created_at__gte=first_day_of_month,
        created_at__lt=last_day_of_month
    ).values('photo').distinct().count()

    # Расчет зарплаты
    try:
        total_salary = TimeEntry.objects.filter(
            user=user,
            start_time__gte=first_day_of_month,
            end_time__lt=last_day_of_month
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    ((F('end_time') - F('start_time')) / timedelta(hours=1)) * Coalesce(F('hourly_rate'), F('user__big_stavka')),
                    output_field=FloatField()
                )
            )
        )['total'] or 0
    except Exception as e:
        logger.error(f'Ошибка при расчете зарплаты для пользователя {user.full_name}: {str(e)}')
        total_salary = 0

    logger.info(f'Статистика для пользователя {user.full_name} успешно сформирована за {selected_month.strftime("%Y-%m")}')
    
    context = {
        'user': user,
        'completed_tasks': completed_tasks,
        'worked_photos': worked_photos,
        'total_salary': total_salary,
        'selected_month': selected_month.strftime('%Y-%m'),
    }
    return render(request, 'director/director_user_statistic.html', context)

@login_required
def director_manager_statistic(request, user_id):
    """Статистика по конкретному менеджеру"""
    current_user = get_object_or_404(CustomUser, id=user_id)
    logger.info(f'Пользователь {request.user} просматривает статистику менеджера {current_user.full_name}')
    
    # Обработка выбора месяца
    selected_month_str = request.GET.get('month')
    selected_month = timezone.now().date()
    if selected_month_str:
        try:
            selected_month = timezone.make_aware(datetime.strptime(selected_month_str, '%Y-%m').date())
        except ValueError:
            pass

    # Определение границ месяца
    first_day = selected_month.replace(day=1)
    if selected_month.month == 12:
        last_day = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
    else:
        last_day = selected_month.replace(month=selected_month.month + 1, day=1)

    # Подсчет созданных задач
    created_tasks_subquery = Task.objects.filter(
        created_by=current_user,
        completed=True,
        created_at__range=(first_day, last_day)
    ).values('created_by').annotate(
        count=Count('id')
    ).values('count')[:1]

    # Подсчет проверенных задач через TaskReview
    reviewed_tasks_subquery = TaskReview.objects.filter(
        manager=current_user,
        task__completed=True,
        reviewed_at__range=(first_day, last_day)
    ).values('manager').annotate(
        count=Count('id')
    ).values('count')[:1]

    # Расчет общего времени работы
    try:
        total_hours = TimeManger.objects.filter(
            user=current_user,
            start_time__gte=first_day,
            end_time__lt=last_day
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    (F('end_time') - F('start_time')) / timedelta(hours=1),
                    output_field=FloatField()
                )
            )
        )['total'] or 0
    except Exception as e:
        logger.error(f'Ошибка при расчете времени работы для менеджера {current_user.full_name}: {str(e)}')
        total_hours = 0

    # Расчет зарплаты
    try:
        total_salary = TimeManger.objects.filter(
            user=current_user,
            start_time__gte=first_day,
            end_time__lt=last_day
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    ((F('end_time') - F('start_time')) / timedelta(hours=1)) * Coalesce(F('hourly_rate'), F('user__big_stavka')),
                    output_field=FloatField()
                )
            )
        )['total'] or 0
    except Exception as e:
        logger.error(f'Ошибка при расчете зарплаты для менеджера {current_user.full_name}: {str(e)}')
        total_salary = 0

    logger.info(f'Статистика для менеджера {current_user.full_name} успешно сформирована за {selected_month.strftime("%Y-%m")}')
    
    context = {
        'user': current_user,
        'created_tasks': created_tasks_subquery,
        'reviewed_tasks': reviewed_tasks_subquery,
        'total_hours': round(total_hours, 2),
        'total_salary': total_salary,
        'selected_month': selected_month.strftime('%Y-%m'),
    }
    return render(request, 'director/director_manager_statistic.html', context) 