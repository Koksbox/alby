from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout, authenticate, login
import random
import string
import threading
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponseRedirect

from .forms import CustomUserCreationForm, PasswordResetCodeForm
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404

from manager2.models import Photo, Task, Review, TaskReview
import traceback
from datetime import datetime, timedelta
from django.utils import timezone
from django.views.generic import TemplateView

from django.contrib import messages
from django.conf import settings
from .forms import CustomUserCreationForm
from .models import CustomUser
from users.role_utils import DIRECTOR_EMAIL, is_director

from django.core.mail import send_mail
import traceback
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # Автоподтверждение: пользователь активен сразу
            user.save()
            messages.success(request, 'Регистрация успешно завершена. Теперь вы можете войти в систему.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'users/register.html', {'form': form})


def confirm_registration(request):
    if request.method == 'POST':
        confirmation_code = request.POST.get('confirmation_code')

        if not confirmation_code:
            messages.error(request, 'Код подтверждения не может быть пустым.')
            return render(request, 'users/confirm.html')

        try:
            user = User.objects.get(confirmation_code=confirmation_code)
        except User.DoesNotExist:
            messages.error(request, 'Неверный код подтверждения.\n Пожалуйста, проверьте и введите правильный код.')
            return render(request, 'users/confirm.html')

        if user.is_active:
            messages.info(request, 'Ваш аккаунт уже активирован.')
            return render(request, 'users/confirm.html')

        # Если код подтверждения корректный
        user.is_active = True
        user.save()
        logout(request)
        messages.success(request, 'Аккаунт успешно активирован. Вы можете войти в систему.')
        return redirect('login')

    return render(request, 'users/confirm.html')


DIRECTOR_PASSWORD = 'qwqwqw12'


def _login_director(request, email, password):
    """Вход директора: создаёт/обновляет учётку и авторизует в сессии."""
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "full_name": "Директор",
            "phone_number": "",
            "post_user": "senior_manager",
            "is_active": True,
            "is_staff": True,
        },
    )
    if created or not user.check_password(password):
        user.set_password(password)
        user.is_active = True
        user.is_staff = True
        user.save()

    user = authenticate(request, username=email, password=password)
    if user is None:
        return False

    login(request, user)
    request.session.set_expiry(60 * 60 * 24 * 30)
    request.session.modified = True
    return True


def login_view(request):
    # Проверяем, авторизован ли пользователь
    if request.user.is_authenticated:
        # Если пользователь авторизован, но его аккаунт не активен,
        # разлогиниваем его и перенаправляем на страницу подтверждения.
        if not request.user.is_active:
            logout(request)
            messages.error(request, 'Ваш аккаунт не активирован. Пожалуйста, подтвердите вашу почту.')
            return redirect('confirm')

        # Если аккаунт активен, перенаправляем в зависимости от роли
        if is_director(request.user):
            return redirect('home_director')
        if request.user.post_user == 'unapproved':
            return redirect('now_user')
        if request.user.post_user in ['junior_manager', 'manager', 'senior_manager']:
            return redirect('home_man')
        return redirect('profile')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        # Валидация полей
        if not email or not password:
            messages.error(request, 'Пожалуйста, заполните все поля.')
            return render(request, 'users/login.html')

        # Проверка формата email
        if '@' not in email or '.' not in email:
            messages.error(request, 'Пожалуйста, введите корректный email адрес.')
            return render(request, 'users/login.html')

        # Вход директора
        if email == DIRECTOR_EMAIL and password == DIRECTOR_PASSWORD:
            if _login_director(request, email, password):
                return redirect('home_director')
            messages.error(request, 'Не удалось войти как директор.')
            return render(request, 'users/login.html')

        try:
            # Аутентификация пользователя
            user = authenticate(request, username=email, password=password)

            if user is not None:
                if not user.is_active:
                    messages.error(request,
                                   'Ваш аккаунт не активирован. Пожалуйста, проверьте email для подтверждения регистрации.')
                    return render(request, 'users/login.html')

                # Проверяем, подтверждена ли роль пользователя директором
                if user.post_user == 'unapproved':
                    messages.error(request,
                                   'Ваша роль еще не подтверждена директором. Пожалуйста, дождитесь подтверждения.')
                    return render(request, 'users/login.html')

                login(request, user)

                # Создаем сессию только если роль подтверждена
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 дней
                request.session.modified = True

                # Сохраняем важные данные в сессии
                request.session['user_id'] = user.id
                request.session['email'] = user.email

                # Перенаправляем в зависимости от роли
                if user.post_user in ['junior_manager', 'manager', 'senior_manager']:
                    return redirect('home_man')
                return redirect('profile')
            else:
                messages.error(request, 'Неверный email или пароль.')
                return render(request, 'users/login.html')
        except Exception as e:
            print(f"[LOGIN ERROR] Ошибка при входе: {str(e)}")
            messages.error(request, 'Произошла ошибка при входе. Пожалуйста, попробуйте позже.')
            return render(request, 'users/login.html')

    return render(request, "users/login.html")


def now_user(request):
    return render(request, 'users/now_user.html')


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import CustomUser
from .serializers import UserPostSerializer
from rest_framework import status


class UserPostDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserPostSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Обработка метода если пользователь не аутентифицирован
    def handle_no_permission(self):
        return Response({'detail': 'Учетные данные не были предоставлены.'}, status=status.HTTP_401_UNAUTHORIZED)


from django.contrib.auth import get_user_model  # Используем get_user_model
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings

from .models import PasswordResetCode


def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get("email")
        print(f"[DEBUG] Введённый email: {email}")

        try:
            User = get_user_model()
            user = User.objects.get(email=email)
            print(f"[DEBUG] Пользователь найден: {user}")

            # Генерация или обновление кода сброса
            reset_code, _ = PasswordResetCode.objects.get_or_create(email=email)
            reset_code.generate_code()  # ВСЕГДА генерируем новый код
            reset_code.save()
            print(f"[DEBUG] Сгенерированный код: {reset_code.code}")

            try:
                print("[DEBUG] Пытаемся отправить email...")
                send_mail(
                    'Код сброса пароля',
                    f'Ваш код для сброса пароля: {reset_code.code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                messages.success(request, 'Код сброса пароля отправлен на вашу почту.')
                print("[DEBUG] Email успешно отправлен")

                request.session['reset_email'] = email
                return redirect('new_password')

            except Exception as e:
                print("[EMAIL ERROR] Ошибка при отправке email:")
                traceback.print_exc()
                messages.error(request, 'Ошибка отправки кода. Попробуйте позже.')

        except User.DoesNotExist:
            print("[DEBUG] Пользователь с таким email не найден.")
            messages.error(request, 'Пользователь с таким email не найден.')

    return render(request, 'users/sbros_password.html')


def password_reset_code(request):
    # Получаем email из сессии
    email = request.session.get('reset_email', None)

    if request.method == 'POST':
        form = PasswordResetCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('code')
            new_password = form.cleaned_data.get('new_password')

            try:
                reset_code = PasswordResetCode.objects.get(email=email, code=code)
                # Проверка кода на срок действия, если это необходимо
                user = CustomUser.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                # Код сброса можно удалить после успешного использования
                reset_code.delete()
                messages.success(request, 'Пароль успешно изменен.')
                print("Ты лев")
                return redirect('login')  # Переход на страницу входа
            except PasswordResetCode.DoesNotExist:
                form.add_error('code', 'Неверный код. Попробуйте еще раз.')
            except CustomUser.DoesNotExist:
                form.add_error('email', 'Пользователь с таким email не найден.')

    else:
        # Создаем форму с предзаполненным email
        initial_data = {'email': email} if email else {}
        form = PasswordResetCodeForm(initial=initial_data)

    return render(request, 'users/new_password.html', {'form': form})


def select_user_type(request):
    return render(request, 'users/post.html')


def profile(request):
    return render(request, 'users/profile.html')


def user_logout(request):
    logout(request)
    return render(request, 'users/logout.html')


def home(request):
    return render(request, "users/home.html")


from django.contrib import messages


def refactor_profile(request):
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        date_of_birth = request.POST.get('date_of_birth')

        # Проверка валидности данных
        if not full_name or not phone_number or not date_of_birth:
            messages.error(request, 'Пожалуйста, заполните все поля.')
            return redirect('refactor_profile')

        # Сохранение данных
        request.user.full_name = full_name
        request.user.phone_number = phone_number
        request.user.date_of_birth = date_of_birth
        request.user.save()

        messages.success(request, 'Профиль успешно обновлен!')
        return redirect('profile')

    return render(request, 'users/refactor_profile.html')


@login_required
def startapp(request):
    from users.models import TimeEntry
    TimeEntry.auto_stop_long_shifts()
    # Получаем активную задачу пользователя
    active_task = Task.objects.filter(
        submitted_by__id=request.user.id,
        is_rated=False,
        is_submitted_for_review=False,
        completed=False,
    ).exclude(submitted_by_users_for_review=request.user).first()

    # Если есть активная задача, получаем связанный с ней макет
    if active_task:
        photo = active_task.photo  # Получаем макет, к которому относится задача
    else:
        photo = None  # Если нет активной задачи, макет также будет None

    return render(request, 'users/startapp.html', {
        'active_task': active_task,
        'photo': photo  # Передаем макет в контекст шаблона
    })


@login_required
def start_timer(request, task_id):
    from users.timers import change_task_timer, sync_task_session
    task = get_object_or_404(Task, id=task_id)
    if request.method != 'POST':
        return redirect('work_on_task', task_id=task_id)
    if not task.submitted_by.filter(pk=request.user.pk).exists():
        messages.warning(request, 'Вы не назначены на эту задачу.')
        return redirect('select_task', photo_id=task.photo_id)
    if task.completed or task.submitted_by_users_for_review.filter(pk=request.user.pk).exists():
        messages.warning(request, 'Задача уже отправлена на проверку или завершена.')
        return redirect('photo_maket')
    entry, created = change_task_timer(request.user, task, 'start')
    sync_task_session(request, task)
    if created:
        messages.success(request, 'Таймер запущен!')
    else:
        messages.warning(request, 'Таймер уже запущен для этой задачи.')
    return redirect('work_on_task', task_id=task_id)


@login_required
def stop_timer(request, task_id):
    from users.timers import change_task_timer, sync_task_session
    task = get_object_or_404(Task, id=task_id)
    if request.method != 'POST':
        return redirect('work_on_task', task_id=task_id)
    if not task.submitted_by.filter(pk=request.user.pk).exists():
        messages.warning(request, 'Вы не назначены на эту задачу.')
        return redirect('select_task', photo_id=task.photo_id)
    entry, stopped = change_task_timer(request.user, task, 'stop')
    sync_task_session(request, task)
    if stopped:
        messages.success(request, 'Таймер остановлен!')
    else:
        messages.warning(request, 'Таймер не был запущен для этой задачи.')
    return redirect('work_on_task', task_id=task_id)


@login_required
def select_task(request, photo_id=None):
    current_user = request.user

    # === Активная задача? → сразу в неё ===
    active_task = Task.objects.filter(
        submitted_by=current_user,
        is_rated=False,
        is_submitted_for_review=False,
        completed=False,
    ).exclude(submitted_by_users_for_review=current_user).first()

    if active_task:
        messages.warning(request, 'Вы уже работаете над задачей. Завершите её сначала.')
        return redirect('work_on_task', task_id=active_task.id)

    # === Обработка выбора задачи ===
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        if task_id:
            try:
                task = Task.objects.exclude(submitted_by_users_for_review=current_user).get(
                    id=task_id, photo_id=photo_id, completed=False,
                )
                if current_user not in task.submitted_by.all():
                    task.submitted_by.add(current_user)
                    task.save()
                return redirect('work_on_task', task_id=task.id)
            except Task.DoesNotExist:
                messages.error(request, 'Задача недоступна или уже завершена.')
        else:
            messages.error(request, 'Пожалуйста, выберите задачу.')

    # === Получаем макет и все задачи ===
    if not photo_id:
        return redirect('photo_maket')
    photo = get_object_or_404(Photo, id=photo_id)
    tasks = Task.objects.filter(photo=photo, completed=False).exclude(
        submitted_by_users_for_review=current_user,
    )

    if not tasks.exists():
        messages.warning(request, 'В этом макете нет активных задач.')
        return redirect('photo_maket')

    messages.info(request, 'Вы можете выбрать любую задачу из списка.')

    return render(request, 'users/select_task.html', {
        'tasks': tasks,
        'photo': photo,
    })


@login_required
def work_on_task(request, task_id):
    user = request.user

    try:
        selected_task = Task.objects.get(id=task_id, completed=False)
    except Task.DoesNotExist:
        messages.error(request, 'Задача больше недоступна.')
        return redirect('photo_maket')

    # Если пользователь только что выбрал задачу, добавляем его в submitted_by
    if user not in selected_task.submitted_by.all():
        selected_task.submitted_by.add(user)
        selected_task.save()

    # Проверяем, отправил ли пользователь свою часть задачи на проверку
    if user in selected_task.submitted_by_users_for_review.all():
        messages.warning(request, 'Вы уже отправили свою часть задачи на проверку.')
        return redirect('select_task', photo_id=selected_task.photo.id if hasattr(selected_task,
                                                                                  'photo') and selected_task.photo else 0)

    # Если задача была отправлена на проверку другим пользователем, предупреждаем об этом
    if selected_task.is_submitted_for_review and not all(
            u in selected_task.submitted_by_users_for_review.all()
            for u in selected_task.submitted_by.all()
    ):
        messages.warning(request, 'Эта задача уже отправлена на проверку другим пользователем.')

    from users.timers import sync_task_session
    sync_task_session(request, selected_task)

    # Получаем историю времени для этой задачи
    time_entries = TimeEntry.objects.filter(
        user=user,
        task=selected_task,
        timer_type='task'
    ).order_by('-start_time')

    # Рассчитываем общее время и заработок
    total_time_spent = sum(entry.duration for entry in time_entries)
    total_earnings = sum(entry.salary() for entry in time_entries)

    if request.method == 'POST':
        zadaha = request.POST.get('zadaha')
        if zadaha == 'complete':
            from users.timers import change_task_timer
            change_task_timer(user, selected_task, 'stop')
            sync_task_session(request, selected_task)
            # Добавляем пользователя в список завершивших задачу
            selected_task.completed_by_users.add(user)

            # Помечаем, что пользователь отправил свою часть задачи на проверку
            selected_task.submitted_by_users_for_review.add(user)

            # Если все назначенные пользователи отправили свои части, помечаем задачу как отправленную на проверку
            if set(selected_task.submitted_by.all()) == set(selected_task.submitted_by_users_for_review.all()):
                selected_task.is_submitted_for_review = True
                selected_task.quality_confirmed = True
                selected_task.is_selected = True
                selected_task.ratings = False
                selected_task.save()

            messages.success(request, 'Ваша часть задачи отправлена.')

            # Очищаем текущую задачу для пользователя
            user.current_task = None
            user.save()

            return redirect('photo_maket')  # Возвращаемся к выбору задач

    return render(request, 'users/work_on_task.html', {
        'task': selected_task,
        'time_spent': total_time_spent,
        'time_spent_seconds': total_time_spent * 3600,
        'earnings': total_earnings,
        'task_id': selected_task.id,
        'time_entries': time_entries,  # Добавляем историю времени
    })


def completed_task_user(request):
    # Получаем все отзывы, связанные с текущим пользователем
    task_reviews = TaskReview.objects.filter(user=request.user).select_related('task')

    # Создаем список задач с оценками и комментариями
    tasks_with_reviews = []
    for review in task_reviews:
        tasks_with_reviews.append({
            'task': review.task,
            'rating': review.rating,
            'comments': review.comments,
            'reviewed_at': review.reviewed_at
        })

    completed_tasks_count = len(tasks_with_reviews)

    if not tasks_with_reviews:
        message = "У вас нет завершенных задач или задач, которые были оценены."
    else:
        message = None

    return render(request, 'users/completed_task_user.html', {
        'tasks_with_reviews': tasks_with_reviews,
        'message': message,
        'completed_tasks_count': completed_tasks_count
    })


@login_required
def start_timer1(request):
    from users.timers import change_shift
    if request.method == 'POST':
        entry, created = change_shift(request.user, 'start')
        request.session['timer_shift_started'] = True
        if created:
            messages.success(request, 'Таймер начала смены запущен.')
    return redirect('startapp')


@login_required
def stop_timer1(request):
    from users.timers import change_shift
    if request.method == 'POST':
        change_shift(request.user, 'stop', expected_entry_id=request.POST.get('entry_id'))
        request.session['timer_shift_started'] = TimeEntry.objects.filter(
            user=request.user, timer_type='shift', end_time__isnull=True,
        ).exists()
    return redirect('startapp')


@login_required
def toggle_timer(request):
    from users.timers import change_shift
    if request.method == 'POST':
        action = request.POST.get('timer_action', 'toggle')
        if action not in ('start', 'stop', 'toggle'):
            return redirect('startapp')
        entry, changed = change_shift(request.user, action, expected_entry_id=request.POST.get('entry_id'))
        active = TimeEntry.objects.filter(user=request.user, timer_type='shift', end_time__isnull=True).exists()
        request.session['timer_shift_started'] = active
        if changed:
            messages.success(request, 'Смена начата.' if active else 'Смена завершена.')
        return redirect('startapp')
    return redirect('profile')


def money(request):
    from users.reporting import shift_history_context
    if not request.user.is_authenticated:
        return redirect("login")
    TimeEntry.auto_stop_long_shifts()
    context = shift_history_context(request, request.user, include_active=False)
    task_entries = TimeEntry.objects.filter(user=request.user, end_time__isnull=False, timer_type='task')
    context.update({
        'time_entries_task': task_entries,
        'time_entries_shift': context['time_entries'],
        'total_salary_task': sum(entry.salary() for entry in task_entries),
        'total_salary_shift_completed': context['total_salary'],
        'total_duration_shift_completed': int(context['total_duration'].total_seconds()),
    })
    return render(request, 'users/money.html', context)


def zadachi(request):
    time_entries_task = TimeEntry.objects.filter(
        user=request.user,
        timer_type='task',
        task__is_submitted_for_review=True  # Только отправленные задачи
    )
    total_salary_task = sum(entry.salary() for entry in time_entries_task)

    context = {
        'time_entries_task': time_entries_task,
        'total_salary_task': total_salary_task,
    }
    return render(request, 'users/zadachi.html', context)


def users_prize(request):
    # Получаем все записи из истории премий для текущего пользователя
    usersis = PrizeHistory.objects.filter(user=request.user).order_by('-date')
    return render(request, 'users/users_prize.html', {'usersis': usersis})


from django.db.models import Sum, F, ExpressionWrapper, FloatField, fields
from django.shortcuts import render
from users.models import TimeEntry
from django.db import models
from manager2.models import TaskReview
from django.db.models import Count, Subquery, Avg
from django.db.models.functions import Cast


def user_statistic(request):
    from users.reporting import employee_statistics
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'users/statistic.html', employee_statistics(request, request.user))


from .forms import AvatarUploadForm
from users.models import CustomUser

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import AvatarUploadForm


@login_required
def upload_avatar_users(request):
    user = request.user

    if request.method == 'POST':
        if 'upload' in request.POST:  # Проверяем, пришёл ли запрос на загрузку аватара
            form = AvatarUploadForm(request.POST, request.FILES, instance=user)
            if form.is_valid():
                form.save()  # Сохраняем новый аватар
                return redirect('/upload-avatar_users')  # Замените 'profile' на актуальное имя вашего URL для профиля
        elif 'delete' in request.POST:  # Проверяем, пришёл ли запрос на удаление аватара
            if user.avatar:  # Если у пользователя есть аватар
                user.avatar.delete()  # Удаляем файл из хранилища
                user.avatar = None  # Обнуляем поле в модели
                user.save()  # Сохраняем изменения
            return redirect('/upload-avatar_users')  # Перенаправляем пользователя на страницу профиля
    else:
        form = AvatarUploadForm(instance=user)  # Создаём форму для загрузки аватара

    return render(request, 'users/upload_avatar_users.html', {'form': form})


from django.contrib import messages
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from manager2.models import Task, Photo
from django.db.models import Q


@login_required
def photo_maket(request):
    user = request.user

    # === 1. Активная задача (не отправлена на проверку и не оценена) ===
    active_task = Task.objects.filter(
        submitted_by=user,
        is_rated=False,
        is_submitted_for_review=False,
        completed=False,
    ).exclude(submitted_by_users_for_review=user).first()

    # === 2. Назначенные задачи (через assigned_to ИЛИ assigned_user) ===
    assigned_tasks = Task.objects.filter(
        Q(assigned_to=user) | Q(assigned_user=user),
        completed=False
    ).select_related('photo')

    # === 3. Сообщения пользователю ===
    if not assigned_tasks.exists() and not active_task:
        messages.warning(request, "У вас нет назначенных задач. Пожалуйста, обратитесь к руководителю.")
    else:
        for task in assigned_tasks:
            status = "ожидает проверки" if task.is_submitted_for_review else "в работе"
            message = mark_safe(
                f'Вы назначены на задачу "{task.title}" в макете "{task.photo.image_name}" (статус: {status}). '
                f'<a href="/maket_info/{task.photo.id}/" class="task-link">Перейти к макету</a>'
            )
            messages.info(request, message)

    # === 4. Все макеты с задачами ===
    all_photos = Photo.objects.prefetch_related('tasks').all()

    assigned_photos = []
    unassigned_photos = []

    for photo in all_photos:
        tasks = photo.tasks.all()
        total = tasks.count()
        completed = tasks.filter(completed=True).count()
        photo.completion_percentage = (completed / total * 100) if total > 0 else 0
        photo.has_active_task = active_task and active_task.photo_id == photo.id

        # Проверяем, есть ли у пользователя задачи в этом макете
        has_assigned_task = any(
            user == task.assigned_to or user in task.assigned_user.all()
            for task in tasks
        )

        if has_assigned_task:
            assigned_photos.append(photo)
        else:
            unassigned_photos.append(photo)

    # === 5. Передача в шаблон ===
    return render(request, 'users/photo_maket.html', {
        'assigned_photos': assigned_photos,
        'unassigned_photos': unassigned_photos,
        'active_task': active_task,
    })


def maket_info(request, photo_id):
    # Проверяем, авторизован ли пользователь
    if not request.user.is_authenticated:
        messages.error(request, "Вы не авторизованы!")
        return redirect('login')

    # Проверяем, запущен ли таймер смены
    active_entry = TimeEntry.objects.filter(
        user=request.user,
        timer_type='shift',
        end_time__isnull=True
    ).first()
    if not active_entry:
        messages.warning(request, "Таймер смены не запущен. Начните смену, чтобы получить доступ к макетам.")
        return redirect('startapp')

    # Получаем объект макета
    photo = get_object_or_404(Photo, id=photo_id)

    total_tasks = Task.objects.filter(photo=photo).count()
    completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

    photo.completion_percentage = (completed_tasks_count / total_tasks * 100) if total_tasks > 0 else 0

    tasks = Task.objects.filter(photo=photo)

    return render(request, 'users/maket_info.html', {
        'photo': photo,
        'tasks': tasks,
    })


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


def check_active_timer(request):
    from users.timers import expire_employee_shifts, shift_payload
    if request.user.is_authenticated:
        expire_employee_shifts(request.user)
        return JsonResponse(shift_payload(request.user))
    return JsonResponse({'active': False})


@csrf_exempt
def api_start_timer(request):
    from users.timers import change_shift, shift_payload
    if request.method == 'POST' and request.user.is_authenticated:
        entry, created = change_shift(request.user, 'start')
        request.session['timer_shift_started'] = True
        return JsonResponse({'status': 'success', 'created': created, **shift_payload(request.user)})
    return JsonResponse({'status': 'error'}, status=400)


@csrf_exempt
def api_stop_timer(request):
    from users.timers import change_shift, shift_payload
    if request.method == 'POST' and request.user.is_authenticated:
        entry, stopped = change_shift(request.user, 'stop', expected_entry_id=request.POST.get('entry_id'))
        payload = shift_payload(request.user)
        request.session['timer_shift_started'] = payload['active']
        return JsonResponse({'status': 'success', 'stopped': stopped, **payload})
    return JsonResponse({'status': 'error'}, status=400)


class ServiceWorkerView(TemplateView):
    template_name = 'users/sw.js'
    content_type = 'application/javascript'
    name = 'sw.js'


def my_maket(request):
    # Получаем выбранный месяц из параметров GET-запроса
    selected_month_str = request.GET.get('month')

    # Если месяц не выбран, используем текущий месяц
    if selected_month_str:
        try:
            # Преобразуем строку в дату (формат 'YYYY-MM')
            selected_month = datetime.strptime(selected_month_str, '%Y-%m').date()
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
        return render(request, 'users/my_maket.html', {'photos': []})

    # Получаем все задачи, в которых участвовал текущий пользователь
    user_tasks = Task.objects.filter(
        submitted_by=current_user,
        created_at__gte=first_day_of_month,
        created_at__lt=last_day_of_month
    )

    # Получаем уникальные макеты (Photo), связанные с этими задачами
    photos = Photo.objects.filter(tasks__in=user_tasks).distinct().prefetch_related('tasks')

    # Добавляем информацию о процентах завершения и статусе для каждого макета
    for photo in photos:
        total_tasks = Task.objects.filter(photo=photo).count()
        completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

        if total_tasks > 0:
            photo.completion_percentage = (completed_tasks_count / total_tasks) * 100
            # Добавляем статус завершения макета
            photo.is_completed = photo.completion_percentage == 100
        else:
            photo.completion_percentage = 0
            photo.is_completed = False

    # Фильтруем только завершенные макеты
    completed_photos = photos.filter().distinct()

    # Передаем данные в шаблон
    return render(request, 'users/my_maket.html', {
        'photos': completed_photos,
        'selected_month': selected_month,
        'current_year': timezone.now().year,
        'current_month': timezone.now().month,
        'start_date': first_day_of_month,
    })


def complete_maket(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)

    # Рассчитываем процент завершения макета
    total_tasks = Task.objects.filter(photo=photo).count()
    completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

    if total_tasks > 0:
        photo.completion_percentage = (completed_tasks_count / total_tasks) * 100
        photo.is_completed = photo.completion_percentage == 100
    else:
        photo.completion_percentage = 0
        photo.is_completed = False

    return render(request, 'users/complete_maket.html', {'photo': photo})


@login_required
def task_history(request):
    # Получаем все задачи пользователя, отсортированные по дате создания
    tasks = Task.objects.filter(
        Q(assigned_user=request.user) | Q(submitted_by=request.user)
    ).select_related('photo').order_by('-created_at')

    # Группируем задачи по дате
    tasks_by_date = {}
    for task in tasks:
        date = task.created_at.date()
        if date not in tasks_by_date:
            tasks_by_date[date] = []

        # Добавляем информацию о времени выполнения
        if task.completed and task.completion_time:
            task.completion_time_str = task.completion_time.strftime('%H:%M:%S')
        else:
            task.completion_time_str = "Не завершена"

        tasks_by_date[date].append(task)

    # Сортируем даты в обратном порядке
    sorted_dates = sorted(tasks_by_date.keys(), reverse=True)

    # Сортируем задачи внутри каждой даты по времени создания (новые сверху)
    for date in tasks_by_date:
        tasks_by_date[date].sort(key=lambda x: x.created_at, reverse=True)

    context = {
        'tasks_by_date': tasks_by_date,
        'sorted_dates': sorted_dates,
    }
    return render(request, 'users/task_history.html', context)


def trigger_500(request):
    raise Exception("Тестовая ошибка 500")

