import os
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.template.context_processors import request

from .models import Photo, Task, Review, TaskReview, TimeManger
from .models import Task  # Подключите модель задачи
from django.utils.timezone import now  # Для работы с датой, если необходимо
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Task
from .forms import TaskForm, ManagerPhotoForm, TaskTemplateForm
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from users.models import TimeEntry
from django.http import JsonResponse
from .models import TaskTemplate


def profile_manager(request):
    return render(request, 'manager2/profile_manager.html')

def home_man(request):
    photos = Photo.objects.all()
    return render(request, 'manager2/home_man.html', {'photos': photos})



def manager_maket(request, photo_id):
    # Получаем объект макета по его ID
    photo = get_object_or_404(Photo, id=photo_id)

    total_tasks = Task.objects.filter(photo=photo).count()
    completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

    if total_tasks > 0:
        photo.completion_percentage = (completed_tasks_count / total_tasks) * 100
    else:
        photo.completion_percentage = 0

    tasks = Task.objects.all()

    context = {
        'photo': photo,
        'tasks': tasks,
    }
    return render(request, 'manager2/manager_maket.html', context)

def history(request):
    user = request.user

    # Получаем активную смену
    active_shift = TimeManger.objects.filter(
        manager=user,
        end_time__isnull=True
    ).first()

    # Рассчитываем прошедшее время для активной смены
    elapsed_time = 0
    if active_shift:
        elapsed_time = int((timezone.now() - active_shift.start_time).total_seconds())

    # Получаем завершенные смены
    time_entries = TimeManger.objects.filter(
        manager=user,
        end_time__isnull=False
    ).order_by('-start_time')

    # Рассчитываем общее время и зарплату для завершенных смен
    total_duration = timezone.timedelta()
    total_salary = 0

    for entry in time_entries:
        if entry.end_time and entry.start_time:
            duration = entry.end_time - entry.start_time
            total_duration += duration
            total_salary += entry.salary

    # Добавляем время и зарплату текущей смены
    if active_shift:
        current_duration = timezone.timedelta(seconds=elapsed_time)
        total_duration += current_duration
        total_salary += (elapsed_time / 3600) * user.stavka()

    context = {
        'time_entries': time_entries,
        'total_salary': total_salary,
        'total_duration': total_duration,
        'active_shift': active_shift,
        'elapsed_time': elapsed_time,
        'user_stavka': user.stavka(),
        'active_shift_start_timestamp': int(active_shift.start_time.timestamp()) if active_shift else 0,
    }

    return render(request, 'manager2/history.html', context)

def upload_photo(request):
    elapsed_time = 0  # Initialize the variable with a default value
    
    if request.user.is_authenticated:
        # Проверяем, запущен ли таймер
        active_time_entry = TimeManger.objects.filter(manager=request.user, end_time__isnull=True).last()
        if active_time_entry:
            elapsed_time = int((now() - active_time_entry.start_time).total_seconds())

        request.session['timer_started'] = active_time_entry is not None

        # Получаем макеты, назначенные текущему менеджеру
        manager_photos = Photo.objects.filter(assigned_manager=request.user)
        
        # Для каждого макета получаем информацию о задачах
        for photo in manager_photos:
            # Получаем все задачи для макета
            tasks = Task.objects.filter(photo=photo)
            
            # Получаем активные задачи (с запущенным таймером)
            active_tasks = []
            assigned_tasks = []
            
            for task in tasks:
                # Проверяем, есть ли активный таймер для задачи
                active_time_entry = TimeEntry.objects.filter(
                    task=task,
                    end_time__isnull=True,
                    timer_type='task'
                ).first()
                
                if active_time_entry:
                    # Если есть активный таймер, задача считается активной
                    active_tasks.append({
                        'task': task,
                        'user': active_time_entry.user,
                        'start_time': active_time_entry.start_time
                    })
                elif task.submitted_by.exists():
                    # Если нет активного таймера, но есть назначенные пользователи
                    assigned_tasks.append({
                        'task': task,
                        'users': task.submitted_by.all()
                    })
            
            # Добавляем информацию о задачах к макету
            photo.active_tasks = active_tasks
            photo.assigned_tasks = assigned_tasks

    return render(request, 'manager2/upload_photo.html', {
        'elapsed_time': elapsed_time,
        'manager_photos': manager_photos
    })

def display_photos(request):
    photos = Photo.objects.all()  # Получаем все загруженные фотографии
    return render(request, 'manager2/photo_list.html', {'photos': photos})


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


def task_list(request):
    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")

        if title and description:  # Убедимся, что данные переданы
            # Сохраняем новую задачу в базе данных
            Task.objects.create(title=title, description=description, created_at=now())
            return redirect('photo_list')  # Перенаправим пользователя на ту же страницу

    # Получим все задачи из базы данных
    tasks = Task.objects.all()

    # Получим фотографии из базы данных
    photos = Photo.objects.all()

    # Передадим задачи и фотографии в шаблон
    return render(request, "manager2/photo_list.html", {"tasks": tasks, "photos": photos})


def delete_task(request, task_id):
    # Получаем задачу по ID или возвращаем 404, если задача не найдена
    task = get_object_or_404(Task, id=task_id)

    # Сохраняем photo_id перед удалением задачи
    photo_id = task.photo.id

    # Удаляем задачу
    task.delete()

    # Перенаправляем пользователя на страницу деталей макета
    return redirect('photo_detail', photo_id=photo_id)


from django.shortcuts import render, get_object_or_404, redirect
from .models import Photo, Task
from .forms import TaskForm


def photo_detail(request, photo_id):
    # Получаем объект макета по его ID
    photo = get_object_or_404(Photo, id=photo_id)

    context = {
        'photo': photo,
    }
    return render(request, 'manager2/photo_detail.html', context)

def photo_list(request):

    photos = Photo.objects.prefetch_related('tasks').all()
    return render(request, 'manager2/photo_list.html', {'photos': photos})


@login_required
def add_task(request, photo_id):
    photo = get_object_or_404(Photo, pk=photo_id)

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            # Создаём задачу, но не сохраняем её сразу
            task = form.save(commit=False)
            task.photo = photo
            task.created_by = request.user

            # Если выбран шаблон, заполняем поля из него
            template = form.cleaned_data.get('template')
            if template:
                task.title = template.title
                task.description = template.description
                task.requirements = template.requirements

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
                    messages.error(request, f'Превышено максимальное количество сотрудников ({task.max_assigned_users}).')
                    return redirect('add_task', photo_id=photo_id)

                # Добавляем пользователей после сохранения задачи
                task.assigned_user.add(*unique_users)

            # Проверяем, достигнут ли лимит max_assigned_users
            if task.is_full():
                messages.warning(request, 'Задача полностью заполнена.')

            return redirect('photo_detail', photo_id=photo_id)
    else:
        form = TaskForm()

    return render(request, 'manager2/add_task.html', {'form': form, 'photo': photo})



from .models import Task


def completed_tasks(request, photo_id):
    # Получаем объект макета по его ID
    photo = get_object_or_404(Photo, id=photo_id)

    # Фильтруем задачи, связанные с этим макетом
    tasks = Task.objects.filter(photo=photo)  # Предполагается, что у модели Task есть поле photo (ForeignKey к Photo)

    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        action = request.POST.get('action')

        if action == 'ratings':
            try:
                task = get_object_or_404(Task, id=task_id)
            except ValueError:
                messages.error(request, "Неверный ID задачи.")
                return redirect('completed_tasks', photo_id=photo_id)

            rating = request.POST.get('rating')
            comments = request.POST.get('comments')
            manager = request.user
            user_id = request.POST.get('user_id')

            if not user_id:
                messages.error(request, "Не указан пользователь для оценки.")
                return redirect('completed_tasks', photo_id=photo_id)

            try:
                user_to_rate = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                messages.error(request, "Пользователь не найден.")
                return redirect('completed_tasks', photo_id=photo_id)

            if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 10:
                messages.error(request, "Пожалуйста, выберите оценку от 1 до 10.")
                return redirect('completed_tasks', photo_id=photo_id)

            rating = int(rating)

            if user_to_rate not in task.submitted_by.all():
                messages.error(request, "Этот пользователь не участвовал в задаче.")
                return redirect('completed_tasks', photo_id=photo_id)

            if TaskReview.objects.filter(task=task, user=user_to_rate).exists():
                messages.error(request, f"Вы уже оценили пользователя {user_to_rate.full_name} за эту задачу.")
                return redirect('completed_tasks', photo_id=photo_id)

            # Создаем новую оценку
            task_review = TaskReview.objects.create(
                task=task,
                user=user_to_rate,
                manager=manager,
                rating=rating,
                comments=comments
            )

            # Проверяем, завершена ли оценка всех участников
            if TaskReview.objects.filter(task=task).count() == task.completed_by_users.count():
                task.is_rated = True
                task.save()
                messages.success(request, "Все участники задачи успешно оценены!")
            else:
                messages.success(request, "Ваш отзыв успешно отправлен!")

            return redirect('completed_tasks', photo_id=photo_id)

        else:
            messages.error(request, "Неизвестное действие.")
            return redirect('completed_tasks', photo_id=photo_id)

    # Фильтруем задачи, чтобы показывать только те, где есть непроработанные оценки
    tasks_with_users_to_rate = []

    for task in tasks:
        # Фильтруем только тех сотрудников, которые завершили свою часть работы и еще не были оценены
        users_to_rate = [
            user for user in task.completed_by_users.all()
            if not TaskReview.objects.filter(task=task, user=user).exists()
        ]

        if users_to_rate:
            tasks_with_users_to_rate.append({
                'task': task,
                'users_to_rate': users_to_rate
            })

    return render(request, 'manager2/completed_tasks.html', {
        'tasks_with_users_to_rate': tasks_with_users_to_rate,
        'photo': photo,  # Передаем объект макета в контекст
    })

def rated_tasks(request, photo_id):
    # Получаем выбранный макет
    photo = get_object_or_404(Photo, id=photo_id)

    # Фильтруем задачи, связанные с этим макетом
    tasks = Task.objects.filter(photo=photo)

    # Получаем задачи, которые уже были оценены (is_rated=True)
    rated_tasks = tasks.filter(is_rated=True)

    # Для каждой задачи собираем информацию об оценках и сотрудниках
    tasks_with_details = []
    for task in rated_tasks:
        # Получаем всех участников задачи и их оценки
        reviews = TaskReview.objects.filter(task=task)
        users_data = []
        for review in reviews:
            user = review.user
            # Находим записи TimeEntry для данного пользователя и задачи
            time_entries = TimeEntry.objects.filter(user=user, task=task)  # Фильтруем по задаче
            total_time_spent = sum(entry.duration for entry in time_entries)  # Общее время (в часах)
            total_earnings = sum(entry.salary() for entry in time_entries)  # Общий заработок
            users_data.append({
                'user': user,
                'rating': review.rating,
                'comments': review.comments,
                'time_spent': total_time_spent,  # Время, потраченное на задачу
                'earnings': total_earnings  # Заработок пользователя
            })
        tasks_with_details.append({
            'task': task,
            'users_data': users_data,
            'photo': photo
        })

    if request.method == 'POST':
        # Обработка завершения или удаления задачи
        task_id = request.POST.get('task_id')
        action = request.POST.get('action')

        try:
            task = get_object_or_404(Task, id=task_id)

            if action == 'complete':
                # Завершаем задачу, если она еще не завершена
                if task.completed:
                    messages.warning(request, f"Задача \"{task.title}\" уже завершена.")
                else:
                    task.completed = True  # Завершаем задачу
                    task.completion_time = timezone.now()  # Устанавливаем время завершения
                    task.save()
                    messages.success(request, f"Задача \"{task.title}\" успешно завершена.")

            elif action == 'delete':
                # Удаляем задачу, независимо от её статуса
                task_title = task.title  # Сохраняем название задачи для сообщения
                task.delete()
                messages.success(request, f"Задача \"{task_title}\" успешно удалена.")

        except ValueError:
            messages.error(request, "Неверный ID задачи.")

        return redirect('rated_tasks', photo_id=photo.id)

    return render(request, 'manager2/rated_tasks.html', {
        'tasks_with_details': tasks_with_details,
        'photo': photo,
    })


def confirm_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)  # Safely get task object
    task.completed = True
    task.quality_confirmed = False  # Hide from employees
    task.save()
    messages.success(request, 'Задача подтверждена.')  # Provide feedback
    return redirect('home_man')  # Redirect to the desired view  # или другое представление


def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    photo = task.photo

    # Проверка существования photo
    if not photo:
        messages.error(request, 'Макет не найден')
        return redirect('task_list_director')


    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Задача обновлена')
            return redirect('photo_detail', photo_id=photo.id)
        else:
            messages.error(request, 'Ошибка в данных формы')
    else:
        form = TaskForm(instance=task)

    return render(request, 'manager2/edit_task.html', {
        'form': form,
        'task': task,
        'photo': photo
    })


from .forms import AvatarUploadForm
from users.models import CustomUser

@login_required
def upload_avatar(request):
    user = request.user

    if request.method == 'POST':
        if 'upload' in request.POST:  # Проверяем, пришёл ли запрос на загрузку аватара
            form = AvatarUploadForm(request.POST, request.FILES, instance=user)
            if form.is_valid():
                form.save()  # Сохраняем новый аватар
                return redirect('profile_manager')  # Замените 'profile' на актуальное имя вашего URL для профиля
        elif 'delete' in request.POST:  # Проверяем, пришёл ли запрос на удаление аватара
            if user.avatar:  # Если у пользователя есть аватар
                user.avatar.delete()  # Удаляем файл из хранилища
                user.avatar = None  # Обнуляем поле в модели
                user.save()  # Сохраняем изменения
            return redirect('profile_manager')  # Перенаправляем пользователя на страницу профиля
    else:
        form = AvatarUploadForm(instance=user)  # Создаём форму для загрузки аватара

    return render(request, 'manager2/upload_avatar.html', {'form': form})


@login_required
def delete_avatar(request):
    if request.method == 'POST':
        user = request.user  # Получаем текущего пользователя

        # Проверяем, есть ли у пользователя аватар
        if user.avatar:
            # Путь к файлу аватара
            avatar_path = os.path.join(settings.MEDIA_ROOT, str(user.avatar.name))  # Получаем путь к файлу

            # Удаляем файл из файловой системы, если он существует
            if os.path.exists(avatar_path):
                os.remove(avatar_path)

            # Удаляем связь с файлом аватара в БД и обнуляем поле
            user.avatar.delete(save=False)  # Удаляем только файл, а не сам объект
            user.avatar = None  # Устанавливаем поле в `None`
            user.save()  # Сохраняем изменения

    # Перенаправляем пользователя на страницу профиля после удаления
    return redirect('profile_manager')


def start_timer_manager(request):
    if request.method == 'POST':
        user = request.user
        if not user.is_authenticated:
            messages.error(request, "Вы не авторизованы!")
            return redirect('login')  # Перенаправьте на страницу входа

        # Проверяем, запущен ли уже таймер
        active_time_entries = TimeManger.objects.filter(manager=user, end_time__isnull=True)
        if active_time_entries.exists():
            messages.error(request, "Таймер уже запущен!")
            return redirect('profile_man')

        # Создаем новую запись времени
        time_entry = TimeManger(manager=user, start_time=timezone.now())
        time_entry.save()
        request.session['timer_started'] = True
        messages.success(request, "Таймер успешно запущен.")
        return redirect('upload_photo')  # Замените на актуальный URL


def stop_timer_manager(request):
    if request.method == 'POST':
        user = request.user
        if not user.is_authenticated:
            messages.error(request, "Вы не авторизованы!")
            return redirect('login')  # Перенаправьте на страницу входа

        # Находим активную запись времени
        active_time_entries = TimeManger.objects.filter(manager=user, end_time__isnull=True)
        if active_time_entries.exists():
            time_entry = active_time_entries.last()  # Берем последнюю активную запись
            time_entry.end_time = timezone.now()
            time_entry.save()
            request.session['timer_started'] = False
            messages.success(request, "Таймер успешно остановлен.")
        else:
            messages.error(request, "Таймер не был запущен!")

        return redirect('upload_photo')  # Замените на актуальный URL
    return redirect('profile_man')


def toggle_timer_manager(request):
    if request.method == 'POST':
        user = request.user
        if not user.is_authenticated:
            messages.error(request, "Вы не авторизованы!")
            return redirect('login')  # Перенаправьте на страницу входа

        # Проверяем, есть ли активные записи времени
        active_time_entries = TimeManger.objects.filter(manager=user, end_time__isnull=True)

        if active_time_entries.exists():
            # Если таймер уже запущен, останавливаем его
            for entry in active_time_entries:
                entry.end_time = timezone.now()
                entry.save()
            request.session['timer_started'] = False
            messages.success(request, "Таймер успешно остановлен.")
        else:
            # Если таймер не запущен, начинаем новый
            time_entry = TimeManger(manager=user, start_time=timezone.now())
            time_entry.save()
            request.session['timer_started'] = True
            messages.success(request, "Таймер успешно запущен.")

        return redirect('upload_photo')  # Замените на нужный URL

    return redirect('profile_man')



def task_completed(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    tasks = Task.objects.filter(photo=photo)
    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")

        if title and description:  # Убедимся, что данные переданы
            # Сохраняем новую задачу в базе данных
            Task.objects.create(title=title, description=description, created_at=now())
            return redirect('photo_list')  # Перенаправим пользователя на ту же страницу

    # Получим все задачи из базы данных
    tasks = Task.objects.all()

    # Получим фотографии из базы данных
    photos = Photo.objects.all()

    # Передадим задачи и фотографии в шаблон
    return render(request, "manager2/task_completed.html", {"tasks": tasks, "photos": photos, 'photo': photo})


def employee(request):
    users = CustomUser.objects.exclude(post_user='manager')
    return render(request, 'manager2/employee.html', {'users': users})



from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from users.models import CustomUser, PromotionRequest

@login_required
def refactor_profile_manager(request):
    user = request.user

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        requested_post = request.POST.get('post_user')

        try:
            # Обновление информации профиля
            user.full_name = full_name
            user.phone_number = phone_number
            user.save()  # Сохраняем изменения профиля
            messages.success(request, 'Данные профиля успешно обновлены.')

            # Если требуется запрос на повышение, создаём его
            if requested_post:
                PromotionRequest.objects.create(user=user, requested_post=requested_post)
                messages.success(request, 'Запрос на повышение отправлен.')

            return redirect('profile_manager')  # Перенаправляем на страницу профиля или другую страницу.
        except IntegrityError:
            messages.error(request, 'Произошла ошибка из-за конфликта данных. Попробуйте ещё раз.')
        except Exception as e:
            messages.error(request, f'Произошла неожиданная ошибка: {str(e)}')

    # Обработка GET запроса для отображения формы редактирования профиля
    return render(request, 'manager2/refactor_profile_manager.html', {'user': user})


def profile_employee_manager(request, user_id):
    print(f"Received user_id: {user_id}")  # Временное сообщение для отладки
    user = get_object_or_404(CustomUser, id=user_id)  # Получаем одного пользователя
    return render(request, 'manager2/profile_employee_manager.html',
{'user': user})  # Передаем единственного пользователя в контекст

from django.shortcuts import render, get_object_or_404, redirect
from director.forms import UserForm

def edit_user_manager(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('/manager/employee/', user_id=user.id)
    else:
        form = UserForm(instance=user)
    return render(request, 'manager2/edit_user_manager.html', {'user': user})




from django.db.models import Sum, F, ExpressionWrapper, FloatField, fields
from django.shortcuts import render
from users.models import TimeEntry
from django.db import models
from manager2.models import TaskReview
from django.db.models import Count,Subquery, Avg, Q, OuterRef, IntegerField
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models.functions import Coalesce

@login_required
def my_statistic(request):
    current_user = request.user

    # Обработка выбора месяца
    selected_month_str = request.GET.get('month')
    selected_month = timezone.now().date()  # Это date
    if selected_month_str:
        try:
            # Парсим как datetime, делаем aware, но оставляем дату месяца
            dt = datetime.strptime(selected_month_str, '%Y-%m')
            selected_month = timezone.make_aware(dt)  # Теперь это datetime
        except (ValueError, TypeError):
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
        reviewed_at__range=(first_day, last_day)
    ).values('manager').annotate(
        count=Count('id')
    ).values('count')[:1]

    total_shift_hours = TimeManger.objects.filter(
        manager=current_user,
        start_time__gte=first_day,  # Заменено на first_day
        start_time__lt=last_day,  # Заменено на last_day
        end_time__isnull=False
    ).aggregate(
        total_hours=Sum(
            (F('end_time') - F('start_time')),
            output_field=fields.DurationField()
        )
    )['total_hours']

    total_shift_hours = total_shift_hours.total_seconds() / 3600 if total_shift_hours else 0

    # Аннотация данных пользователя
    user_data = CustomUser.objects.filter(id=current_user.id).annotate(
        created_tasks=Coalesce(
            Subquery(created_tasks_subquery, output_field=IntegerField()),
            0
        ),
        reviewed_tasks=Coalesce(
            Subquery(reviewed_tasks_subquery, output_field=IntegerField()),
            0
        )
    ).first()

    # Расчет зарплаты
    try:
        salary_data = TimeManger.boss_total_salary_for_each_user(
            start_date=first_day,
            end_date=last_day,
            manager_id=current_user.id  # Передаем manager_id
        )
        total_salary = salary_data.get(current_user.id, 0)
    except Exception as e:
        print(f"Ошибка расчета зарплаты: {str(e)}")  # Для отладки
        total_salary = 0

    # Получение макетов созданных задач
    created_tasks = Task.objects.filter(
        created_by=current_user,
        completed=True,
        created_at__range=(first_day, last_day)
    ).select_related('photo')

    worked_photos_manager = Task.objects.filter(
        created_by=current_user,
        completed=True,
        created_at__range=(first_day, last_day)
    ).distinct().count()


    photo_names = [
        task.photo.image_name
        for task in created_tasks
        if task.photo and hasattr(task.photo, 'image_name')
    ]
    worked_photos = ', '.join(set(photo_names)) if photo_names else 'Нет макетов'


    context = {
        'user_data': user_data,
        'total_salary': total_salary,
        'worked_photos': worked_photos,
        'worked_photos_manager': worked_photos_manager,
        'selected_month': selected_month,
        'current_year': timezone.now().year,
        'current_month': timezone.now().month,
        'start_date': first_day,
        'end_date': last_day,
        'total_shift_hours': total_shift_hours,
    }

    return render(request, 'manager2/my_statistic.html', context)



@login_required
def manager_user_statistic(request, user_id):
    current_user = get_object_or_404(CustomUser, id=user_id)

    # Обработка выбора месяца
    selected_month = timezone.now().date()
    if 'month' in request.GET:
        try:
            dt = datetime.strptime(request.GET['month'], '%Y-%m')
            selected_month = timezone.make_aware(dt)  # Теперь это datetime
        except ValueError:
            pass

    # Определение границ месяца
    first_day = selected_month.replace(day=1)
    if selected_month.month == 12:
        last_day = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
    else:
        last_day = selected_month.replace(month=selected_month.month + 1, day=1)

    # Расчет зарплаты
    try:
        salary_data = TimeEntry.boss_total_salary_for_each_user(
            start_date=first_day,
            end_date=last_day,
            user_id=current_user.id
        )
        total_salary = salary_data.get(current_user.id, 0)
    except Exception:
        total_salary = 0

    # Подзапрос для подсчета задач
    completed_tasks_subquery = Task.objects.filter(
        submitted_by=OuterRef('pk'),
        completed=True,
        created_at__range=(first_day, last_day)
    ).values('submitted_by').annotate(
        count=Count('id')
    ).values('count')

    # Аннотация данных пользователя
    user_data = CustomUser.objects.filter(id=current_user.id).annotate(
        avg_rating_annotation=Avg('reviews_user__rating'),
        completed_tasks_count=Subquery(completed_tasks_subquery, output_field=models.IntegerField()) or 0
    ).first()

    # Отдельный запрос для макетов
    completed_tasks_with_photos = Task.objects.filter(
        submitted_by=current_user,
        completed=True,
        created_at__range=(first_day, last_day)
    ).select_related('photo')

    worked_photos = Task.objects.filter(
        submitted_by=current_user,
        completed=True,
        created_at__range=(first_day, last_day)
    ).distinct().count()


    context = {
        'user': current_user,
        'user_data': user_data,
        'total_salary': total_salary,
        'worked_photos': worked_photos,
        'selected_month': selected_month,
        'current_year': timezone.now().year,
        'current_month': timezone.now().month,
        'start_date': first_day,
        'end_date': last_day,
    }

    return render(request, 'manager2/manager_statistic_users.html', context)


def my_maket_manager(request):
    # Получаем выбранный месяц из параметров GET-запроса
    selected_month_str = request.GET.get('month')

    # Если месяц не выбран, используем текущий месяц
    if selected_month_str:
        try:
            # Преобразуем строку в дату (формат 'YYYY-MM')
            dt = datetime.strptime(selected_month_str, '%Y-%m')
            selected_month = timezone.make_aware(dt)  # Теперь это datetime
        except (ValueError, TypeError):
            # Если данные некорректны, используем текущий месяц
            selected_month = timezone.now().date()
    else:
        selected_month = timezone.now().date()

    # Определяем первый и последний день выбранного месяца
    first_day_of_month = selected_month.replace(day=1)
    if selected_month.month == 12:
        last_day_of_month = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
    else:
        last_day_of_month = selected_month.replace(month=selected_month.month + 1, day=1)

    current_user = request.user

    if current_user.is_anonymous:
        # Если пользователь не аутентифицирован, возвращаем пустой список макетов
        return render(request, 'manager2/my_maket_manager.html', {'photos': []})

    # Получаем все задачи, в которых участвовал текущий пользователь
    user_tasks = Task.objects.filter(
        created_by=current_user,
        created_at__gte=first_day_of_month,
        created_at__lt=last_day_of_month
    )

    # Получаем уникальные макеты (Photo), связанные с этими задачами
    photos = Photo.objects.filter(tasks__in=user_tasks).distinct().prefetch_related('tasks')

    # Добавляем информацию о процентах завершения для каждого макета
    for photo in photos:
        total_tasks = Task.objects.filter(photo=photo).count()
        completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

        if total_tasks > 0:
            photo.completion_percentage = (completed_tasks_count / total_tasks) * 100
        else:
            photo.completion_percentage = 0

    # Фильтруем только завершенные макеты
    completed_photos = photos.filter().distinct()

    # Передаем данные в шаблон
    return render(request, 'manager2/my_maket_manager.html', {
        'photos': completed_photos,
        'selected_month': selected_month,
        'current_year': timezone.now().year,
        'current_month': timezone.now().month,
        'start_date': first_day_of_month,
    })


def maket_info_manager(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    return render(request, 'manager2/maket_info_manager.html', {'photo': photo})

def employee_shifts(request, user_id):
    employee = get_object_or_404(CustomUser, id=user_id)

    # Получаем активную смену
    active_shift = TimeEntry.objects.filter(
        user=employee,
        end_time__isnull=True,
        timer_type='shift'
    ).first()

    # Рассчитываем прошедшее время для активной смены
    elapsed_time = 0
    if active_shift:
        elapsed_time = int((timezone.now() - active_shift.start_time).total_seconds())

    # Получаем выбранный месяц из параметров GET-запроса
    selected_month_str = request.GET.get('month')

    # Если месяц не выбран, используем текущий месяц
    if selected_month_str:
        try:
            selected_month = timezone.make_aware(datetime.strptime(selected_month_str, '%Y-%m').date())
        except (ValueError, TypeError):
            selected_month = timezone.now().date()
    else:
        selected_month = timezone.now().date()

    # Определяем первый и последний день выбранного месяца
    first_day_of_month = selected_month.replace(day=1)
    if selected_month.month == 12:
        last_day_of_month = selected_month.replace(year=selected_month.year + 1, month=1, day=1)
    else:
        last_day_of_month = selected_month.replace(month=selected_month.month + 1, day=1)

    # Получаем записи времени для сотрудника за выбранный период
    time_entries = TimeEntry.objects.filter(
        user=employee,
        timer_type='shift',
        start_time__gte=first_day_of_month,
        start_time__lt=last_day_of_month,
        end_time__isnull=False
    ).order_by('-start_time')
    
    # Рассчитываем общее время и зарплату
    total_duration = timezone.timedelta()
    for entry in time_entries:
        if entry.end_time and entry.start_time:
            total_duration += entry.end_time - entry.start_time

    total_salary = sum(entry.salary() for entry in time_entries)
    
    context = {
        'employee': employee,
        'time_entries': time_entries,
        'selected_month': selected_month,
        'total_duration': total_duration,
        'total_salary': total_salary,
        'active_shift': active_shift,
        'elapsed_time': elapsed_time,
        'user_stavka': employee.stavka(),
    }
    
    return render(request, 'manager2/employee_shifts.html', context)

def upload_photo_manager(request):
    """Загрузка нового макета менеджером"""
    if request.method == 'POST':
        photos = request.FILES.getlist('photo')
        form = ManagerPhotoForm(request.POST)
        if form.is_valid():
            for photo in photos:
                new_photo = Photo(
                    image=photo,
                    image_name=form.cleaned_data['image_name'],
                    description=form.cleaned_data['description'],
                    requirements=form.cleaned_data['requirements'],
                    due_date=form.cleaned_data['due_date'],
                    assigned_manager=request.user,  # Автоматически назначаем текущего менеджера
                )
                new_photo.save()
            return redirect('home_man')
        else:
            return render(request, 'manager2/upload_photo_manager.html', {'form': form})
    else:
        form = ManagerPhotoForm()
    return render(request, 'manager2/upload_photo_manager.html', {'form': form})

def edit_photo(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    
    if request.method == 'POST':
        form = ManagerPhotoForm(request.POST, instance=photo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Макет успешно обновлен')
            return redirect('photo_detail', photo_id=photo.id)
    else:
        form = ManagerPhotoForm(instance=photo)
    
    return render(request, 'manager2/photo_detail.html', {'photo': photo, 'form': form})

def complete_photo(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    tasks = Task.objects.filter(photo=photo)
    
    if not all(task.completed for task in tasks):
        messages.error(request, f"Невозможно завершить макет. Сначала завершите все задачи для макета {photo.image_name}.")
        return redirect('photo_detail', photo_id=photo.id)

    if not photo.is_completed:
        photo.is_completed = True
        photo.save()
        messages.success(request, 'Макет успешно завершен')
    
    return redirect('photo_detail', photo_id=photo.id)

@login_required
def task_templates_manager(request, photo_id):
    """Представление для управления шаблонами задач менеджером."""
    templates = TaskTemplate.objects.all()
    return render(request, 'manager2/task_templates.html', {
        'templates': templates,
        'form': TaskTemplateForm(),
        'photo_id': photo_id
    })

@login_required
def delete_template(request, template_id, photo_id):
    """Представление для удаления шаблона задачи."""
    template = get_object_or_404(TaskTemplate, id=template_id)
    template.delete()
    messages.success(request, 'Шаблон успешно удален')
    return redirect('task_templates_manager', photo_id=photo_id)

@login_required
def get_template_data(request, template_id):
    """View для получения данных шаблона через AJAX."""
    try:
        template = TaskTemplate.objects.get(id=template_id)
        data = {
            'title': template.title,
            'description': template.description,
            'requirements': template.requirements
        }
        return JsonResponse(data)
    except TaskTemplate.DoesNotExist:
        return JsonResponse({'error': 'Template not found'}, status=404)

def task_templates(request, photo_id):
    templates = TaskTemplate.objects.all()
    return render(request, 'manager2/task_templates.html', {
        'templates': templates,
        'form': TaskTemplateForm(),
        'photo': Photo.objects.get(id=photo_id)
    })

def create_template_manager(request, photo_id):
    """Представление для создания нового шаблона задачи менеджером."""
    if request.method == 'POST':
        form = TaskTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            template.save()
            messages.success(request, 'Шаблон успешно создан')
            return redirect('task_templates_manager', photo_id=photo_id)
    else:
        form = TaskTemplateForm()
    
    return render(request, 'manager2/create_template.html', {
        'form': form,
        'photo_id': photo_id
    })

def task_monitoring(request):
    # Получаем все активные задачи (с запущенным таймером)
    active_time_entries = TimeEntry.objects.filter(
        end_time__isnull=True,
        timer_type='task'
    ).select_related('task', 'user', 'task__photo')

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

    # Получаем историю таймеров за последние 7 дней
    week_ago = timezone.now() - timezone.timedelta(days=7)
    task_history = TimeEntry.objects.filter(
        timer_type='task',
        end_time__isnull=False,
        start_time__gte=week_ago
    ).select_related('task', 'user', 'task__photo').order_by('-start_time')

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

    context = {
        'active_tasks': active_tasks,
        'task_history': formatted_history,
        'tasks_for_review': tasks_for_review
    }
    
    return render(request, 'manager2/task_monitoring.html', context)