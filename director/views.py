import datetime as dt
from datetime import timedelta

from users.models import CustomUser, PrizeHistory
from django.shortcuts import render, get_object_or_404, redirect
from .forms import UserForm
from users.views import CustomUser
from django.contrib import messages
from users.models import PromotionRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from manager2.models import Task, Photo
import os
from django.conf import settings
from manager2.forms import TaskForm
from django.shortcuts import get_object_or_404, redirect, render
from manager2.models import Photo, PhotoFile
from .forms import UploadFileForm

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from manager2.models import Photo
from .forms import PhotoDescriptionForm
from django.db.models import Q
from .forms import AddDescriptionForm

from django.shortcuts import render, get_object_or_404, redirect
from .forms import PhotoForm  # Создайте форму для редактирования

from django import forms
from manager2.models import TaskTemplate
from django.http import JsonResponse

from users.models import CustomUser, PrizeHistory, TimeEntry

def edit_maket(request, id):
    photo = get_object_or_404(Photo, id=id)
    if request.method == 'POST':
        form = PhotoForm(request.POST, request.FILES, instance=photo)
        if form.is_valid():
            form.save()
            return redirect('task_list_director')  # Перенаправление после успешного редактирования
    else:
        form = PhotoForm(instance=photo)

    return render(request, 'director/edit_maket.html', {'form': form, 'photo': photo})


def maket_info_director(request, photo_id):
    # Получаем объект макета по его ID
    photo = get_object_or_404(Photo, id=photo_id)

    context = {
        'photo': photo,
    }
    return render(request, 'director/maket_info_director.html', context)


def add_description(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)  # Найти макет по ID

    if request.method == 'POST':
        form = AddDescriptionForm(request.POST)
        if form.is_valid():
            photo.description = form.cleaned_data['description']  # Обновить описание
            photo.save()
            return redirect('task_list_director')  # Перенаправьте на страницу макета или другой URL

    else:
        form = AddDescriptionForm()

    return render(request, 'director/add_description.html', {'form': form, 'photo': photo})


def photo_detail(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)

    if request.method == 'POST':
        form = PhotoDescriptionForm(request.POST, instance=photo)
        if form.is_valid():
            form.save()
            return redirect('task_list_director')  # Или обратно на ту же страницу
    else:
        form = PhotoDescriptionForm(instance=photo)

    return render(request, 'director/photo_detail.html', {'photo': photo, 'form': form})



def maket_director(request, photo_id):
    # Получаем объект макета по его ID
    photo = get_object_or_404(Photo, id=photo_id)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "complete":
            # Проверяем, завершены ли все задачи, связанные с этим макетом
            tasks = Task.objects.filter(photo=photo)
            if not all(task.completed for task in tasks):
                # Если не все задачи завершены, показываем сообщение об ошибке
                messages.error(
                    request,
                    f"Невозможно завершить макет. Сначала завершите все задачи для макета {photo.image_name}."
                )
                return redirect("maket_director", photo_id=photo_id)

            # Если все задачи завершены, можно завершить макет
            if not photo.is_completed:
                photo.is_completed = True
                photo.save()
                messages.success(request, f"Макет '{photo.image_name}' успешно завершен!")
                return redirect("task_list_director")

    context = {
        'photo': photo,
    }
    return render(request, 'director/maket_director.html', context)


def upload_file_to_photo(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            photo_file = form.save(commit=False)
            photo_file.photo = photo
            photo_file.save()
            return redirect('task_list_director')  # Замените на правильный путь после сохранения

    else:
        form = UploadFileForm()

    return render(request, 'upload_file.html', {'form': form, 'photo': photo})


def upload_photo(request):
    if request.method == 'POST':
        photos = request.FILES.getlist('photo')  # Загружаем все загруженные фотографии
        for photo in photos:
            new_photo = Photo(image=photo)
            new_photo.save()
        return redirect('task_list_director')  # Перенаправляем на страницу с изображениями

    return render(request, 'director/upload_photo_director.html')


def delete_photo(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)

    if request.method == 'POST':

        # Удаление задач
        Task.objects.filter(photo=photo).delete()

        # Удаление файла
        if photo.image:
            photo.image.delete(save=False)

        photo_name = photo.image_name
        photo.delete()

        messages.success(request, f'Макет "{photo_name}" удалён.')

        # Редирект по referer
        referer = request.META.get('HTTP_REFERER', '')
        if 'director' in referer:
            return redirect('task_list_director')
        else:
            return redirect('task_list')

    return redirect('task_list')

def upload_photo_director(request):
    if request.method == 'POST':
        photos = request.FILES.getlist('photo')  # Загружаем все загруженные фотографии
        form = AddDescriptionForm(request.POST)  # Используем форму для получения данных
        if form.is_valid():
            for photo in photos:
                new_photo = Photo(
                    image=photo,
                    image_name=form.cleaned_data['image_name'],  # Название
                    description=form.cleaned_data['description'],  # Описание
                    requirements=form.cleaned_data['requirements'],  # Требования
                    due_date=form.cleaned_data['due_date'],  # Срок сдачи
                    assigned_manager=form.cleaned_data['assigned_manager'],  # Назначенный менеджер
                )
                new_photo.save()
            return redirect('task_list_director')  # Перенаправляем на страницу с изображениями
        else:
            # Если форма невалидна, вернуть её обратно с ошибками
            return render(request, 'director/upload_photo_director.html', {'form': form})
    else:
        form = AddDescriptionForm()  # Создаем пустую форму для GET-запроса
    return render(request, 'director/upload_photo_director.html', {'form': form})


def delete_task_director(request, task_id):
    # Получаем задачу по ID или возвращаем 404, если задача не найдена
    task = get_object_or_404(Task, id=task_id)

    # Сохраняем photo_id перед удалением задачи
    photo_id = task.photo.id

    # Удаляем задачу
    task.delete()

    # Перенаправляем пользователя на страницу деталей макета
    return redirect('maket_director', photo_id=photo_id)



def task_list_director(request):
    if request.method == "POST":
        action = request.POST.get("action")
        photo_id = request.POST.get("photo_id")

        if action == "complete":
            # Получаем макет по photo_id
            photo = get_object_or_404(Photo, id=photo_id)

            # Проверяем, завершены ли все задачи, связанные с этим макетом
            tasks = Task.objects.filter(photo=photo)
            if not all(task.completed for task in tasks):
                # Если не все задачи завершены, показываем сообщение об ошибке
                return render(request, "director/task_list_director.html", {
                    "tasks": Task.objects.all(),
                    "photos": Photo.objects.all(),
                    "error_message": f"Невозможно завершить макет. Сначала завершите все задачи для макета {photo.image_name}."
                })

            # Если все задачи завершены, можно завершить макет
            if not photo.is_completed:
                photo.is_completed = True
                photo.save()

            return redirect('task_list_director')

    # Получаем все фотографии из базы данных
    photos = Photo.objects.all()

    # Добавляем информацию о процентах завершения для каждого макета
    for photo in photos:
        total_tasks = Task.objects.filter(photo=photo).count()
        completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

        if total_tasks > 0:
            photo.completion_percentage = (completed_tasks_count / total_tasks) * 100
        else:
            photo.completion_percentage = 0

    # Получаем все задачи и фотографии из базы данных
    tasks = Task.objects.all()

    # Передаем задачи и фотографии в шаблон
    return render(request, "director/task_list_director.html", {"tasks": tasks, "photos": photos})


from django.db.models import Exists, OuterRef
from django.db.models import Q

def employee_director(request):
    # Подзапрос: есть ли у пользователя активный таймер (TimeEntry без end_time)
    active_timer = TimeEntry.objects.filter(
        user=OuterRef('pk'),
        end_time__isnull=True
    )

    # Получаем параметр сортировки из GET-запроса
    sort_by = request.GET.get('sort_by', 'name')  # По умолчанию сортировка по имени

    # Получаем всех пользователей, исключая менеджеров и непринятых
    users = CustomUser.objects.exclude(
        Q(post_user__in=['junior_manager', 'manager', 'senior_manager']) | Q(post_user='unapproved')
    ).annotate(
        timer_active=Exists(active_timer)  # ← Добавляем аннотацию
    )

    # Применяем сортировку
    if sort_by == 'name':
        users = users.order_by('full_name')
    elif sort_by == 'position':
        users = users.order_by('post_user')

    context = {
        'users': users,
        'current_sort': sort_by,
    }
    return render(request, 'director/employee.html', context)

from django.db.models import Exists, OuterRef, Q
from manager2.models import CustomUser, TimeManger  # ← импортируем TimeManger вместо TimeEntry

def employee_manager(request):
    # Подзапрос: есть ли у менеджера активная смена в TimeManger?
    active_shift = TimeManger.objects.filter(
        manager=OuterRef('pk'),  # ← важно: поле 'manager', а не 'user'
        end_time__isnull=True
    )

    users = CustomUser.objects.filter(
        post_user__in=['junior_manager', 'manager', 'senior_manager']
    ).annotate(
        timer_active=Exists(active_shift)  # ← аннотация по TimeManger
    )

    return render(request, 'director/employee_manager.html', {'users': users})

def profile_employee(request, user_id):
    from django.contrib.auth.decorators import login_required
    from users.role_utils import is_director, reset_user_password

    if not request.user.is_authenticated:
        return redirect("login")
    if not is_director(request.user):
        messages.error(request, "Недостаточно прав.")
        return redirect("home")

    user = get_object_or_404(CustomUser, id=user_id)

    temp_password = None
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reset_password":
            temp_password = reset_user_password(user)
            messages.success(
                request,
                "Пароль сброшен. Временный пароль показан ниже (после обновления страницы исчезнет).",
            )
        else:
            messages.error(request, "Неизвестное действие.")

    return render(
        request,
        "director/profile_employee.html",
        {"user": user, "temp_password": temp_password},
    )


def promotion_requests(request):
    requests = PromotionRequest.objects.all()

    return render(request, 'director/promotion_requests.html', {'requests': requests})


from django.shortcuts import render, get_object_or_404, redirect
from .forms import UserForm


def edit_user(request, user_id):
    if not request.user.is_authenticated:
        return redirect('login')
    if not is_director(request.user):
        messages.error(request, 'Недостаточно прав.')
        return redirect('home')
    user = get_object_or_404(CustomUser, id=user_id)

    if request.method == 'POST':
        # Проверяем, запрошено ли удаление
        if request.POST.get('action') == 'deactivate':
            # Защита: нельзя деактивировать самого себя (на случай ошибки интерфейса)
            if user == request.user:
                messages.error(request, "Вы не можете деактивировать свой собственный аккаунт.")
            else:
                user.is_active = False
                user.save()
                messages.success(request, f'Сотрудник «{user.full_name}» успешно удалён.')
            return redirect('/director/employee_director/')

        # Иначе — сохраняем изменения
        previous_post = user.post_user
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=False)
            if user.post_user != previous_post:
                user.big_stavka = user.calculate_default_stavka()
            user.save()
            messages.success(request, 'Изменения сохранены.')
            return redirect('/director/employee_director/')

    else:
        form = UserForm(instance=user)

    return render(request, 'director/edit_user.html', {'form': form, 'user': user})


def director_promotions(request):
    promotion_requests = PromotionRequest.objects.all()  # Получение всех запросов на повышение

    if request.method == 'POST':
        promotion_request_id = request.POST.get('promotion_request_id')
        approve = request.POST.get('approve')  # Получаем информацию о подтверждении

        # Проверка и обработка запроса
        try:
            promotion_request = PromotionRequest.objects.get(id=promotion_request_id)
            if approve:  # Если запрос подтверждается
                user = promotion_request.user
                user.post_user = promotion_request.requested_post  # Обновляем пост пользователя
                user.save()
                messages.success(request, 'Запрос на повышение подтвержден и должность обновлена.')
            else:
                promotion_request.delete()  # Возможно, удалить отклоненный запрос
                messages.info(request, 'Запрос на повышение отклонен.')

            # Удаляем запрос после обработки
            promotion_request.delete()

        except PromotionRequest.DoesNotExist:
            messages.error(request, 'Запрос на повышение не найден.')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')

    context = {
        'promotion_requests': promotion_requests,
    }
    return render(request, 'director/director_promotions.html', context)


from django.shortcuts import render
from django.db.models import Count, Sum, Avg, Q
from users.models import CustomUser, TimeEntry
from manager2.models import Task  # Пример, если модели пользователей и задач называются так


def home_director(request):
    # Общее число пользователей
    total_users = CustomUser.objects.count()

    # Кол-во активных пользователей
    active_users = CustomUser.objects.filter(is_active=True).count()

    # Выполненные задачи
    completed_tasks = Task.objects.filter(completed=True).count()

    completed_maket = Photo.objects.filter(is_completed=True).count()

    # Среднее время выполнения задач
    average_task_time = Task.objects.aggregate(Avg('time_spent'))['time_spent__avg'] or 0

    # Общая зарплата (сумма всех salary из TimeEntry)
    total_salary = TimeEntry.total_salary_users()
    total_salary_manager = TimeManger.total_salary_users_money()
    full_zarplata = total_salary + total_salary_manager

    # Общая сумма премий
    total_prizes = PrizeHistory.objects.aggregate(total=Sum('amount'))['total'] or 0

    # Передаем данные в шаблон
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'completed_tasks': completed_tasks,
        'completed_maket': completed_maket,
        'average_task_time': average_task_time,
        'total_salary': total_salary,
        'full_zarplata': full_zarplata,
        'total_salary_manager': total_salary_manager,
        'total_prizes': total_prizes,
    }
    return render(request, 'director/home.html', context)


def director_dashboard(request):
    unapproved_users = CustomUser.objects.filter(post_user='unapproved', is_active = True)
    user_type_choices = CustomUser.USER_TYPE_CHOICES  # Получаем доступные роли

    return render(request, 'director/director_dashboard.html', {
        'unapproved_users': unapproved_users,
        'user_type_choices': user_type_choices,
    })


def approve_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)

    # Получаем роль из формы
    user_role = request.POST.get('user_role')
    if user_role:
        user.post_user = user_role
        user.save()
        messages.success(request, f'Пользователь {user.email} был подтверждён как {user_role}.')

    return redirect('director_dashboard')


User = get_user_model()

# views.py
def add_task_director(request, photo_id):
    photo = get_object_or_404(Photo, pk=photo_id)

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            # Создаём задачу, но не сохраняем её сразу
            task = form.save(commit=False)
            task.photo = photo

            # Если пользователь анонимный, можем создать "псевдопользователя" для директора
            if request.user.is_authenticated:
                task.created_by = request.user
            else:
                # Предположим, что у вас есть созданный "директор" пользователь,
                # который обозначает, что задача была создана директором
                task.created_by = None  # Используйте своего "директора"

            # Сохраняем задачу в базе данных
            task.save()

            # Получаем выбранных пользователей из формы
            assigned_users = form.cleaned_data.get('assigned_user', [])

            if assigned_users:
                # Исключаем пользователей, которые уже работали с задачей
                unique_users = [
                    user for user in assigned_users
                    if user not in task.submitted_by.all()
                ]

                # Проверяем, не превышает ли количество уникальных пользователей лимит
                if len(unique_users) > task.max_assigned_users:
                    messages.error(request,
                                   f'Превышено максимальное количество сотрудников ({task.max_assigned_users}).')
                    return redirect('add_task_director', photo_id=photo_id)

                # Добавляем пользователей после сохранения задачи
                task.assigned_user.add(*unique_users)

            # Проверяем, достигнут ли лимит max_assigned_users
            if task.is_full():
                messages.warning(request, 'Задача полностью заполнена.')

            return redirect('maket_director', photo_id=photo_id)  # Redirect to the list of photos with tasks
    else:
        form = TaskForm()

    return render(request, 'director/add_task_director.html', {'form': form, 'photo': photo})





def task_list_director_completed(request):
    photos = Photo.objects.all()
    return render(request, "director/task_list_director_completed.html", { "photos": photos})


def completed_maket(request, photo_id):

    photo = get_object_or_404(Photo, id=photo_id)

    completed_maket = Task.objects.filter(photo=photo, completed=True)

    context = {
        'photo': photo,
        'completed_maket': completed_maket,
    }
    return render(request, 'director/completed_maket.html', context)


def director_prize(request):
    post_user = request.GET.get('post_user')
    sort_by = request.GET.get('sort_by', 'alphabetical_asc') # По умолчанию сортировка по алфавиту
    min_stavka = request.GET.get('min_stavka')
    max_stavka = request.GET.get('max_stavka')

    # Получаем всех пользователей, исключая неутвержденных
    users = CustomUser.objects.filter(is_active=True).exclude(post_user='unapproved')

    # Применяем фильтр по должности
    if post_user:
        users = users.filter(post_user=post_user)

    # Применяем фильтр по ставке
    if min_stavka:
        try:
            min_stavka = float(min_stavka)
            users = users.filter(big_stavka__gte=min_stavka)
        except ValueError:
            pass # Игнорируем некорректное значение

    if max_stavka:
        try:
            max_stavka = float(max_stavka)
            users = users.filter(big_stavka__lte=max_stavka)
        except ValueError:
            pass # Игнорируем некорректное значение

    # Применяем сортировку
    if sort_by == 'alphabetical_asc':
        users = users.order_by('full_name')
    elif sort_by == 'alphabetical_desc':
        users = users.order_by('-full_name')
    elif sort_by == 'stavka_asc':
        users = users.order_by('big_stavka')
    elif sort_by == 'stavka_desc':
        users = users.order_by('-big_stavka')

    # Получаем доступные роли для фильтра (исключая неутвержденных)
    post_user_choices = [choice for choice in CustomUser.USER_TYPE_CHOICES if choice[0] != 'unapproved']

    context = {
        'users': users,
        'post_user_choices': post_user_choices,
        'selected_post_user': post_user,
        'sort_by': sort_by,
        'min_stavka': min_stavka,
        'max_stavka': max_stavka,
    }
    return render(request, "director/director_prize.html", context)


def set_prize(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)

    if request.method == 'POST':
        try:
            # Получаем значение премии из POST-запроса
            prize_amount = float(request.POST.get('prize', 0))

            # Проверяем, что премия находится в допустимом диапазоне
            if prize_amount < 100 or prize_amount > 50000:
                messages.error(request, "Премия должна быть в диапазоне от 100 до 50000 рублей.")
                return redirect('director_prize')

            # Сохраняем текущую премию в истории
            PrizeHistory.objects.create(user=user, amount=prize_amount)

            # Обновляем текущую премию пользователя
            user.prize = prize_amount
            user.save()

            messages.success(request, f"Премия для {user.full_name} успешно обновлена.")
        except ValueError:
            messages.error(request, "Некорректное значение премии.")

    return redirect('director_prize')


from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from users.models import PrizeHistory  # Импортируем вашу модель PrizeHistory

def prize_history(request):
    selected_month_str = request.GET.get('month')

    if selected_month_str:
        try:
            selected_month = dt.datetime.strptime(selected_month_str, '%Y-%m').date()
        except (ValueError, TypeError):
            selected_month = timezone.now().date()
    else:
        selected_month = timezone.now().date()

    first_day_of_month = selected_month.replace(day=1)
    if selected_month.month == 12:
        last_day_of_month = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
    else:
        last_day_of_month = selected_month.replace(month=selected_month.month + 1, day=1)

    # Получаем историю премий, включая объекты пользователей
    history = (
        PrizeHistory.objects
        .filter(date__gte=first_day_of_month, date__lt=last_day_of_month)
        .select_related('user')  # Загрузка связанного пользователя
    )

    # Группируем и суммируем премии
    aggregated_history = {}
    for entry in history:
        if entry.user.full_name in aggregated_history:
            aggregated_history[entry.user.full_name] += entry.amount
        else:
            aggregated_history[entry.user.full_name] = entry.amount

    context = {
        'history': [(name, total) for name, total in aggregated_history.items()],  # Преобразуем в список для шаблона
        'selected_month': selected_month.strftime('%Y-%m'),
    }

    return render(request, 'director/prize_history.html', context)



from django.db.models import Sum, F, ExpressionWrapper, FloatField, fields
from django.shortcuts import render
from users.models import TimeEntry, CustomUser
from django.db import models
from manager2.models import TaskReview
from django.db.models import Prefetch
from django.db.models import Count,Subquery, Avg, Q, OuterRef, IntegerField
from django.utils import timezone
from django.db.models.functions import Coalesce
from django.db.models import Value, FloatField

def salary_report(request):
    from users.reporting import salary_report_context
    if not request.user.is_authenticated:
        return redirect('login')
    if not is_director(request.user):
        messages.error(request, 'Недостаточно прав.')
        return redirect('home')
    return render(request, 'director/salary_report.html', salary_report_context(request, manager=False))


from manager2.models import TimeManger

def salary_manager(request):
    from users.reporting import salary_report_context
    if not request.user.is_authenticated:
        return redirect('login')
    if not is_director(request.user):
        messages.error(request, 'Недостаточно прав.')
        return redirect('home')
    return render(request, 'director/salary_manager.html', salary_report_context(request, manager=True))



def director_user_statistic(request, user_id):
    from users.reporting import employee_statistics
    if not request.user.is_authenticated:
        return redirect('login')
    if not is_director(request.user):
        messages.error(request, 'Недостаточно прав.')
        return redirect('home')
    employee = get_object_or_404(CustomUser, id=user_id)
    return render(request, 'director/director_user_statistic.html', employee_statistics(request, employee))

def director_manager_statistic(request, user_id):
    from users.reporting import manager_statistics
    if not request.user.is_authenticated:
        return redirect('login')
    if not is_director(request.user):
        messages.error(request, 'Недостаточно прав.')
        return redirect('home')
    employee = get_object_or_404(CustomUser, id=user_id)
    return render(request, 'director/director_manager_statistic.html', manager_statistics(request, employee, director=True))

def is_director(user):
    from users.role_utils import is_director as _is_director
    return _is_director(user)


def employee_shiftsdir(request, user_id):
    from users.reporting import shift_history_context
    if not request.user.is_authenticated:
        return redirect('login')
    if not is_director(request.user):
        messages.error(request, 'Недостаточно прав.')
        return redirect('home')
    employee = get_object_or_404(CustomUser, id=user_id)
    return render(request, 'director/employee_shifts.html',
                  shift_history_context(request, employee, include_active=False))

def manager_shifts(request, user_id):
    from users.reporting import shift_history_context
    if not request.user.is_authenticated:
        return redirect('login')
    if not is_director(request.user):
        messages.error(request, 'Недостаточно прав.')
        return redirect('home')
    employee = get_object_or_404(CustomUser, id=user_id)
    return render(request, 'director/manager_shifts.html', shift_history_context(request, employee, manager=True))

class TaskTemplateForm(forms.ModelForm):
    class Meta:
        model = TaskTemplate
        fields = ['title', 'description', 'requirements']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

def task_templates_director(request, photo_id):
    templates = TaskTemplate.objects.all()
    return render(request, 'director/task_templates.html', {
        'templates': templates,
        'form': TaskTemplateForm(),
        'photo_id': photo_id
    })

def delete_template(request, template_id, photo_id):
    """Представление для удаления шаблона задачи."""
    if request.method == 'POST':
        template = get_object_or_404(TaskTemplate, id=template_id)
        template.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

def get_template_data(request, template_id):
    """Представление для получения данных шаблона через AJAX."""
    try:
        template = TaskTemplate.objects.get(id=template_id)
        data = {
            'title': template.title,
            'description': template.description,
            'requirements': template.requirements
        }
        return JsonResponse(data)
    except TaskTemplate.DoesNotExist:
        return JsonResponse({'error': 'Шаблон не найден'}, status=404)

def edit_template_director(request, template_id):
    """Представление для редактирования шаблона задачи."""
    template = get_object_or_404(TaskTemplate, id=template_id)
    if request.method == 'POST':
        form = TaskTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, 'Шаблон успешно обновлен')
            return redirect('task_templates_director', photo_id=request.POST.get('photo_id'))
    else:
        form = TaskTemplateForm(instance=template)

    return render(request, 'director/edit_template.html', {
        'form': form,
        'template': template,
        'photo_id': request.GET.get('photo_id')
    })

def create_template_director(request, photo_id):
    """Представление для создания нового шаблона задачи."""
    if request.method == 'POST':
        form = TaskTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            # Получаем первого доступного пользователя с ролью директора
            director = CustomUser.objects.filter(post_user='director').first()
            if director:
                template.created_by = director
            else:
                # Если директора нет, используем первого доступного пользователя
                user = CustomUser.objects.filter(is_active=True).first()
                if user:
                    template.created_by = user
                else:
                    messages.error(request, 'Не удалось создать шаблон: нет доступных пользователей')
                    return redirect('task_templates_director', photo_id=photo_id)
            template.save()
            messages.success(request, 'Шаблон успешно создан')
            return redirect('task_templates_director', photo_id=photo_id)
    else:
        form = TaskTemplateForm()

    return render(request, 'director/create_template.html', {
        'form': form,
        'photo_id': photo_id
    })

def task_monitoring(request):
    # Получаем параметры фильтрации
    selected_photo = request.GET.get('photo')
    selected_task = request.GET.get('task')

    # Получаем все активные задачи (с запущенным таймером)
    active_time_entries = TimeEntry.objects.filter(
        end_time__isnull=True,
        timer_type='task'
    ).select_related('task', 'user', 'task__photo')

    # Применяем фильтры к активным задачам
    if selected_photo:
        active_time_entries = active_time_entries.filter(task__photo__id=selected_photo)
    if selected_task:
        active_time_entries = active_time_entries.filter(task__id=selected_task)

    # Формируем список активных задач с дополнительной информацией
    active_tasks = []
    for entry in active_time_entries:
        elapsed_time = timezone.now() - entry.start_time
        hours = int(elapsed_time.total_seconds() // 3600)
        minutes = int((elapsed_time.total_seconds() % 3600) // 60)
        elapsed_time_str = f"{hours:02d}:{minutes:02d}"

        active_tasks.append({
            'task': entry.task,
            'user': entry.user,
            'start_time': entry.start_time,
            'elapsed_time': elapsed_time_str
        })

    # Получаем задачи, отправленные на проверку
    tasks_for_review = Task.objects.filter(
        is_submitted_for_review=True,
        is_rated=False
    ).select_related('photo', 'assigned_to').order_by('-last_modified')

    # Применяем фильтры к задачам на проверке
    if selected_photo:
        tasks_for_review = tasks_for_review.filter(photo__id=selected_photo)
    if selected_task:
        tasks_for_review = tasks_for_review.filter(id=selected_task)

    # Получаем историю таймеров за последние 7 дней
    week_ago = timezone.now() - timezone.timedelta(days=7)
    task_history = TimeEntry.objects.filter(
        timer_type='task',
        end_time__isnull=False,
        start_time__gte=week_ago
    ).select_related('task', 'user', 'task__photo').order_by('-start_time')

    # Применяем фильтры к истории
    if selected_photo:
        task_history = task_history.filter(task__photo__id=selected_photo)
    if selected_task:
        task_history = task_history.filter(task__id=selected_task)

    # Создаем список для хранения истории с отформатированной длительностью
    formatted_history = []
    for entry in task_history:
        duration = entry.end_time - entry.start_time
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        duration_str = f"{hours:02d}:{minutes:02d}"

        formatted_history.append({
            'entry': entry,
            'duration': duration_str
        })

    # Получаем список всех макетов и задач для фильтров
    all_photos = Photo.objects.all().order_by('image_name')
    all_tasks = Task.objects.all().order_by('title')

    context = {
        'active_tasks': active_tasks,
        'task_history': formatted_history,
        'tasks_for_review': tasks_for_review,
        'all_photos': all_photos,
        'all_tasks': all_tasks,
        'selected_photo': selected_photo,
        'selected_task': selected_task
    }

    return render(request, 'director/task_monitoring.html', context)

