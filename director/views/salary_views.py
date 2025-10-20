from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, ExpressionWrapper, FloatField, fields, OuterRef, Subquery, IntegerField, Value, Coalesce, Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import logging
from users.models import CustomUser, TimeEntry, PrizeHistory
from manager2.models import Task, TaskReview, TimeManger

logger = logging.getLogger('director')

@login_required
def director_prize(request):
    """Управление премиями"""
    logger.info(f'Пользователь {request.user} открыл страницу управления премиями')
    users = CustomUser.objects.exclude(post_user='unapproved')
    return render(request, "director/director_prize.html", {'users': users})

@login_required
def set_prize(request, user_id):
    """Установка премии для пользователя"""
    user = get_object_or_404(CustomUser, id=user_id)
    logger.info(f'Пользователь {request.user} устанавливает премию для {user.full_name}')

    if request.method == 'POST':
        try:
            prize_amount = float(request.POST.get('prize', 0))
            if prize_amount < 100 or prize_amount > 50000:
                logger.warning(f'Некорректная сумма премии {prize_amount} для пользователя {user.full_name}')
                messages.error(request, "Премия должна быть в диапазоне от 100 до 50000 рублей.")
                return redirect('director_prize')

            PrizeHistory.objects.create(user=user, amount=prize_amount)
            user.prize = prize_amount
            user.save()
            logger.info(f'Премия {prize_amount} успешно установлена для пользователя {user.full_name}')
            messages.success(request, f"Премия для {user.full_name} успешно обновлена.")
        except ValueError:
            logger.error(f'Ошибка при установке премии для пользователя {user.full_name}')
            messages.error(request, "Некорректное значение премии.")

    return redirect('director_prize')

@login_required
def prize_history(request):
    """История премий"""
    logger.info(f'Пользователь {request.user} просматривает историю премий')
    
    selected_month_str = request.GET.get('month')
    selected_month = timezone.now().date()

    if selected_month_str:
        try:
            selected_month = timezone.make_aware(datetime.strptime(selected_month_str, '%Y-%m').date())
        except (ValueError, TypeError):
            logger.error(f'Некорректный формат месяца: {selected_month_str}')
            pass

    first_day_of_month = selected_month.replace(day=1)
    last_day_of_month = (selected_month.replace(month=selected_month.month + 1, day=1) 
                        if selected_month.month < 12 
                        else selected_month.replace(year=selected_month.year + 1, month=1, day=1))

    history = (
        PrizeHistory.objects
        .filter(date__gte=first_day_of_month, date__lt=last_day_of_month)
        .select_related('user')
    )

    aggregated_history = {}
    for entry in history:
        if entry.user.full_name in aggregated_history:
            aggregated_history[entry.user.full_name] += entry.amount
        else:
            aggregated_history[entry.user.full_name] = entry.amount

    logger.info(f'История премий успешно сформирована для периода {selected_month.strftime("%Y-%m")}')
    context = {
        'history': [(name, total) for name, total in aggregated_history.items()],
        'selected_month': selected_month.strftime('%Y-%m'),
    }

    return render(request, 'director/prize_history.html', context)

@login_required
def salary_report(request):
    """Отчет по зарплатам сотрудников"""
    logger.info(f'Пользователь {request.user} запросил отчет по зарплатам')
    
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

    # Разрешенные роли (без менеджерских)
    non_manager_roles = [code for code, _ in CustomUser.USER_TYPE_CHOICES if code not in ['junior_manager', 'manager', 'senior_manager']]

    # Базовый запрос: только активные пользователи с не-менеджерскими ролями
    users = CustomUser.objects.filter(is_active=True, post_user__in=non_manager_roles)

    # Добавляем аннотации для среднего рейтинга и выполненных задач
    users = users.annotate(
        average_ratings=Avg('reviews_user__rating', filter=Q(reviews_user__rating__isnull=False)),
        completed_tasks_count=Count('taskreview', filter=Q(taskreview__task__completed=True))
    )

    if start_date and end_date_plus_one:
        try:
            # Добавляем аннотацию для общей зарплаты
            users = users.annotate(
                total_salary=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            ((F('timeentry__end_time') - F('timeentry__start_time')) / timedelta(hours=1)) * Coalesce(F('timeentry__hourly_rate'), F('big_stavka')),
                            output_field=FloatField()
                        ),
                        filter=Q(timeentry__start_time__gte=start_date, timeentry__end_time__lt=end_date_plus_one)
                    ),
                    Value(0.0),
                    output_field=FloatField()
                )
            )
            
            # Получаем общую зарплату и индивидуальные зарплаты
            total_salary = TimeEntry.total_salary_users_money_user(start_date=start_date, end_date=end_date_plus_one)
            individual_salaries = TimeEntry.total_salary_for_each_user_user(start_date=start_date, end_date=end_date_plus_one)
            
            logger.info(f'Отчет по зарплатам успешно сформирован для периода {start_date.strftime("%Y-%m-%d")} - {end_date.strftime("%Y-%m-%d")}')
        except ValueError as e:
            logger.error(f'Ошибка при формировании отчета по зарплатам: {str(e)}')
            total_salary = 0
            individual_salaries = {}
    else:
        total_salary = None
        individual_salaries = {}

    # Повторно убеждаемся, что менеджеры исключены (на случай внешних аннотаций)
    users = users.exclude(post_user__in=['manager', 'junior_manager', 'senior_manager'])

    # Фильтруем по должности, если указана
    if post_user:
        # Игнорируем менеджерские роли в фильтре
        if post_user in ['junior_manager', 'manager', 'senior_manager']:
            post_user = None
        else:
            users = users.filter(post_user=post_user)

    # Сортировка
    if sort_by == 'asc':
        users = users.order_by('big_stavka')
    elif sort_by == 'desc':
        users = users.order_by('-big_stavka')
    elif sort_by == 'wasc' and 'average_ratings' in users.query.annotations:
        users = users.order_by('average_ratings')
    elif sort_by == 'wdesc' and 'average_ratings' in users.query.annotations:
        users = users.order_by('-average_ratings')
    elif sort_by == 'task' and 'completed_tasks_count' in users.query.annotations:
        users = users.order_by('completed_tasks_count')
    elif sort_by == 'anti_task' and 'completed_tasks_count' in users.query.annotations:
        users = users.order_by('-completed_tasks_count')

    # Список ролей для фильтра (без менеджерских)
    post_user_choices_filtered = [choice for choice in CustomUser.USER_TYPE_CHOICES if choice[0] in non_manager_roles]

    context = {
        'users': users,
        'total_salary': total_salary,
        'individual_salaries': individual_salaries,
        'post_user_choices': post_user_choices_filtered,
        'selected_post_user': post_user,
        'sort_by': sort_by,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
    }
    return render(request, 'director/salary_report.html', context)

@login_required
def salary_manager(request):
    """Отчет по зарплатам менеджеров"""
    logger.info(f'Пользователь {request.user} запросил отчет по зарплатам менеджеров')
    
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

    # Базовый запрос для менеджеров
    users = CustomUser.objects.filter(is_active=True, post_user__in=['manager', 'junior_manager', 'senior_manager'])

    # Добавляем аннотацию для выполненных задач
    users = users.annotate(
        completed_tasks_count=Count('task', filter=Q(task__completed=True))
    )

    if start_date and end_date_plus_one:
        try:
            # Добавляем аннотацию для общей зарплаты
            users = users.annotate(
                total_salary=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            ((F('timemanger_set__end_time') - F('timemanger_set__start_time')) / timedelta(hours=1)) * Coalesce(F('timemanger_set__hourly_rate'), F('big_stavka')),
                            output_field=FloatField()
                        ),
                        filter=Q(timemanger_set__start_time__gte=start_date,
                                timemanger_set__end_time__lt=end_date_plus_one)
                    ),
                    Value(0.0),
                    output_field=FloatField()
                )
            )
            
            # Получаем общую зарплату и индивидуальные зарплаты
            total_salary = TimeManger.total_salary_users_money(start_date=start_date, end_date=end_date_plus_one)
            individual_salaries = TimeManger.total_salary_for_each_user(start_date=start_date, end_date=end_date_plus_one)
            
            logger.info(f'Отчет по зарплатам менеджеров успешно сформирован для периода {start_date.strftime("%Y-%m-%d")} - {end_date.strftime("%Y-%m-%d")}')
        except ValueError as e:
            logger.error(f'Ошибка при формировании отчета по зарплатам менеджеров: {str(e)}')
            total_salary = 0
            individual_salaries = {}
    else:
        total_salary = None
        individual_salaries = {}

    # Фильтруем по должности, если указана
    if post_user:
        users = users.filter(post_user=post_user)

    # Сортировка
    if sort_by == 'asc':
        users = users.order_by('big_stavka')
    elif sort_by == 'desc':
        users = users.order_by('-big_stavka')
    elif sort_by == 'wasc' and 'average_ratings' in users.query.annotations:
        users = users.order_by('average_ratings')
    elif sort_by == 'wdesc' and 'average_ratings' in users.query.annotations:
        users = users.order_by('-average_ratings')
    elif sort_by == 'task' and 'completed_tasks_count' in users.query.annotations:
        users = users.order_by('completed_tasks_count')
    elif sort_by == 'anti_task' and 'completed_tasks_count' in users.query.annotations:
        users = users.order_by('-completed_tasks_count')

    context = {
        'users': users,
        'total_salary': total_salary,
        'individual_salaries': individual_salaries,
        'post_user_choices': CustomUser.USER_TYPE_CHOICES,
        'selected_post_user': post_user,
        'sort_by': sort_by,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
    }

    return render(request, 'director/salary_manager.html', context) 