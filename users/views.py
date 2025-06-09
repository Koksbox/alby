from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout, authenticate, login
import random
import string

from django.db.models import Count, F
from django.http import HttpResponseRedirect

from .forms import CustomUserCreationForm, PasswordResetCodeForm
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404

from manager2.models import Photo, Task, Review, TaskReview
import traceback
from datetime import datetime
from django.utils import timezone
from django.views.generic import TemplateView


User = get_user_model()


from django.core.mail import send_mail
import random
import string

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            user.save()

            email = form.cleaned_data.get('email')
            if not email:
                messages.error(request, 'Email не может быть пустым')
                return render(request, 'users/register.html', {'form': form})

            # Отправка кода на почту
            try:
                subject = 'Код подтверждения регистрации'
                message = f'Ваш код подтверждения: {user.confirmation_code}'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [email]

                if not from_email:
                    raise ValueError('DEFAULT_FROM_EMAIL не настроен в settings.py')

                send_mail(
                    subject,
                    message,
                    from_email,
                    recipient_list,
                    fail_silently=False,
                )
                print(f'[DEBUG] Код подтверждения: {user.confirmation_code}')
                print(f'[DEBUG] Отправка на email: {email}')

                messages.success(request, 'Код подтверждения отправлен на вашу почту. Введите его для завершения регистрации.')
                return redirect('confirm')

            except Exception as e:
                print(f"[EMAIL ERROR]: {str(e)}")
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
                messages.error(request, 'Не удалось отправить письмо. Пожалуйста, проверьте правильность email адреса и попробуйте позже.')
                return render(request, 'users/register.html', {'form': form})

    else:
        form = CustomUserCreationForm()

    return render(request, 'users/register.html', {'form': form})


from .models import User, PrizeHistory, TimeEntry, CustomUser  # Импортируем вашу модель пользователя

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


DIRECTOR_EMAIL = 'albygroup@bk.ru'
DIRECTOR_PASSWORD = 'qwqwqw12'


def login_view(request):
    # Проверяем, авторизован ли пользователь
    if request.user.is_authenticated:
        if request.user.post_user == 'unapproved':
            return redirect('now_user')
        if request.user.post_user == 'manager':
            return redirect('home_man')
        return redirect('profile')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Проверка, является ли email и пароль директорскими
        if email == DIRECTOR_EMAIL and password == DIRECTOR_PASSWORD:
            return redirect('home_director')

        # Аутентификация пользователя
        user = authenticate(request, username=email, password=password)

        # Проверка, существует ли пользователь и имеет ли он статус 'unapproved'
        if user is not None:
            login(request, user)
            
            # Настройка длительной сессии
            request.session.set_expiry(60 * 60 * 24 * 30)  # 30 дней
            request.session.modified = True  # Принудительное обновление сессии
            
            # Сохраняем важные данные в сессии
            request.session['user_id'] = user.id
            request.session['email'] = user.email
            
            if user.post_user == 'unapproved':
                return redirect('now_user')
            if user.post_user == 'manager':
                return redirect('home_man')
            else:
                return redirect('profile')
        else:
            # Если аутентификация не удалась, выводим сообщение об ошибке
            messages.error(request, 'Неправильный email или пароль.')

    return render(request, 'users/login.html')


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
    return render(request, 'users/home.html')


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


def startapp(request):
    # Получаем активную задачу пользователя
    active_task = Task.objects.filter(
        submitted_by__id=request.user.id,
        is_rated=False,
        is_submitted_for_review=False
    ).first()

    # Если есть активная задача, получаем связанный с ней макет
    if active_task:
        photo = active_task.photo  # Получаем макет, к которому относится задача
    else:
        photo = None  # Если нет активной задачи, макет также будет None

    return render(request, 'users/startapp.html', {
        'active_task': active_task,
        'photo': photo  # Передаем макет в контекст шаблона
    })


def start_timer(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user = request.user

    if user not in task.submitted_by.all():
        messages.warning(request, 'Вы не назначены на эту задачу.')
        return redirect('select_task')

    active_time_entry = TimeEntry.objects.filter(user=user, task=task, end_time__isnull=True).first()
    if active_time_entry:
        messages.warning(request, 'Таймер уже запущен для этой задачи.')
    else:
        TimeEntry.objects.create(
            user=user,
            task=task,
            start_time=timezone.now()
        )
        messages.success(request, 'Таймер запущен!')
        request.session['timer_running'] = True  # Устанавливаем флаг запуска таймера
        request.session['start_time'] = timezone.now().isoformat()  # Сохраняем время старта

    return redirect('work_on_task', task_id)


def stop_timer(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user = request.user

    if user not in task.submitted_by.all():
        messages.warning(request, 'Вы не назначены на эту задачу.')
        return redirect('select_task')

    active_time_entry = TimeEntry.objects.filter(user=user, task=task, end_time__isnull=True).first()
    if active_time_entry:
        active_time_entry.end_time = timezone.now()
        active_time_entry.save()
        messages.success(request, 'Таймер остановлен!')
        request.session['timer_running'] = False  # Сбрасываем флаг запуска таймера
    else:
        messages.warning(request, 'Таймер не был запущен для этой задачи.')

    return redirect('work_on_task', task_id)



def select_task(request, photo_id=None):
    current_user = request.user
    selected_task = None
    message = None

    # Получаем макет по ID (если указан)
    if photo_id:
        photo = get_object_or_404(Photo, id=photo_id)
    else:
        photo = None

    # Проверяем, есть ли у пользователя активная задача, которая ещё не отправлена на проверку
    active_task = Task.objects.filter(
        submitted_by=current_user,
        is_rated=False,
        is_submitted_for_review = False
    ).first()

    if active_task:
        # Если есть активная задача, показываем только её
        messages.warning(request, 'Вы уже работаете над задачей. Завершите её сначала.')
        return redirect('work_on_task', task_id=active_task.id)
    else:
        # Если нет активной задачи, показываем все доступные задачи
        if request.user.is_authenticated:
            base_query = Task.objects.filter(completed=False)
            if photo:
                base_query = base_query.filter(photo=photo)
            
            # Получаем все задачи, на которые назначен пользователь
            assigned_tasks = base_query.filter(assigned_user=current_user)
            
            # Если есть назначенные задачи, показываем только их
            if assigned_tasks.exists():
                tasks = assigned_tasks
                messages.info(request, 'Вот задачи, на которые вы назначены:')
            else:
                # Если нет назначенных задач, показываем все доступные
                tasks = [
                    task for task in base_query
                    if (
                        not task.is_full() and
                        current_user not in task.completed_by_users.all()
                    )
                ]
                if tasks:
                    messages.warning(request, 'Вы не назначены ни на одну из доступных задач. Пожалуйста, обратитесь к руководителю для назначения.')

        else:
            tasks = []

    # Обработка POST-запроса для выбора задачи
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        if task_id is not None:
            try:
                task_id = int(task_id)
                selected_task = get_object_or_404(Task, id=task_id, completed=False)

                # Проверяем, принадлежит ли задача указанному макету
                if photo and selected_task.photo != photo:
                    messages.error(request, 'Эта задача не относится к выбранному макету.')
                    return redirect('select_task', photo_id=photo_id)

                # Проверяем, является ли пользователь уже назначенным или работавшим над задачей
                if current_user in selected_task.submitted_by.all():
                    messages.info(request, 'Вы уже выбрали эту задачу ранее.')
                    return redirect('work_on_task', task_id=selected_task.id)

                # Проверяем, есть ли свободные места для новых пользователей
                if not selected_task.is_full():
                    selected_task.submitted_by.add(current_user)
                    selected_task.save()

                    message = f'Вы успешно выбрали задачу: {selected_task.title}'
                    messages.success(request, message)
                    return redirect('work_on_task', task_id=selected_task.id)
                else:
                    messages.error(request, 'Задача достигла максимального количества пользователей для рецензирования.')
                    return redirect('select_task')

            except ValueError:
                message = "Invalid task ID"
                selected_task = None

    return render(request, 'users/select_task.html', {
        'tasks': tasks, 
        'photo': photo,
        'assigned_tasks': assigned_tasks if 'assigned_tasks' in locals() else None
    })



def work_on_task(request, task_id):
    user = request.user

    try:
        selected_task = Task.objects.get(id=task_id, completed=False)
    except Task.DoesNotExist:
        messages.error(request, 'Задача больше недоступна.')
        return redirect('select_task')  # Перенаправляем на страницу выбора задач

    # Проверяем, является ли пользователь назначенным на задачу
    if user not in selected_task.submitted_by.all():
        messages.error(request, 'Вы не назначены на эту задачу.')
        return redirect('select_task')

    # Проверяем, отправил ли пользователь свою часть задачи на проверку
    if user in selected_task.submitted_by_users_for_review.all():
        messages.warning(request, 'Вы уже отправили свою часть задачи на проверку.')
        return redirect('select_task')

    # Если задача была отправлена на проверку другим пользователем, предупреждаем об этом
    if selected_task.is_submitted_for_review and not all(
        user in selected_task.submitted_by_users_for_review.all()
        for user in selected_task.submitted_by.all()
    ):
        messages.warning(request, 'Эта задача уже отправлена на проверку другим пользователем.')

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


def start_timer1(request):
    if request.method == 'POST':
        user = request.user
        time_entry = TimeEntry(user=user, start_time=timezone.now(), timer_type='shift')
        time_entry.save()
        messages.success(request, 'Таймер начала смены запущен.')
        return redirect('startapp')

def stop_timer1(request):
    if request.method == 'POST':
        user = request.user
        active_time_entries = TimeEntry.objects.filter(user=user, end_time__isnull=True, timer_type='shift')
        if active_time_entries.exists():
            time_entry = active_time_entries.last()
            time_entry.end_time = timezone.now()
            time_entry.save()
            messages.success(request, 'Таймер окончания смены остановлен.')
        else:
            messages.warning(request, 'Таймер начала смены не был запущен.')
        return redirect('startapp')


def toggle_timer(request):
    if request.method == 'POST':
        user = request.user
        if not user.is_authenticated:
            messages.error(request, "Вы не авторизованы!")
            return redirect('login')

        # Определяем тип таймера (смена)
        timer_type = 'shift'

        # Проверяем активную смену
        active_entry = TimeEntry.objects.filter(
            user=user,
            timer_type=timer_type,
            end_time__isnull=True
        ).first()

        if active_entry:
            # Останавливаем смену
            active_entry.end_time = timezone.now()
            active_entry.save()
            request.session[f'timer_{timer_type}_started'] = False
            messages.success(request, "Смена завершена.")
        else:
            # Начинаем новую смену
            TimeEntry.objects.create(
                user=user,
                timer_type=timer_type,
                start_time=timezone.now()
            )
            request.session[f'timer_{timer_type}_started'] = True
            messages.success(request, "Смена начата.")

        return redirect('startapp')
    return redirect('profile')


def money(request):
    # Получаем все записи TimeEntry для текущего пользователя
    time_entries_task = TimeEntry.objects.filter(user=request.user, end_time__isnull=False, timer_type='task')
    # Получаем только ЗАВЕРШЕННЫЕ смены
    time_entries_shift = TimeEntry.objects.filter(user=request.user, end_time__isnull=False, timer_type='shift')

    # Получаем активную смену (если есть)
    active_shift = TimeEntry.objects.filter(user=request.user, end_time__isnull=True, timer_type='shift').first()

    # Рассчитываем общую зарплату и длительность только для ЗАВЕРШЕННЫХ смен
    total_salary_shift_completed = sum(entry.salary() for entry in time_entries_shift)
    total_duration_shift_completed = sum(entry.duration for entry in time_entries_shift)

    # Рассчитываем прошедшее время и потенциальную зарплату для активной смены (если есть)
    elapsed_time_active = 0
    current_salary_active = 0
    if active_shift:
        elapsed_time_active = int((timezone.now() - active_shift.start_time).total_seconds())
        user_stavka = request.user.stavka()
        current_salary_active = (elapsed_time_active / 3600) * user_stavka


    # Рассчитываем общую зарплату для задач
    total_salary_task = sum(entry.salary() for entry in time_entries_task)

    # Получаем ставку пользователя для использования в JS
    user_stavka = request.user.stavka()

    # Передаем данные в шаблон
    context = {
        'time_entries_task': time_entries_task,
        'time_entries_shift': time_entries_shift, # Завершенные смены для списка
        'total_salary_task': total_salary_task,  # Общая зарплата для задач
        'total_salary_shift_completed': total_salary_shift_completed,  # Общая зарплата для завершенных смен
        'total_duration_shift_completed': total_duration_shift_completed,  # Общая длительность завершенных смен
        'active_shift': active_shift,  # Активная смена
        'elapsed_time': elapsed_time_active,  # Прошедшее время активной смены (начальное)
        'user_stavka': user_stavka,  # Ставка пользователя
    }
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
from django.db.models import Count,Subquery, Avg
from django.db.models.functions import Cast

def user_statistic(request):
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

    # Текущий пользователь
    current_user = request.user


    # Для аутентифицированного пользователя
    total_shift_hours = TimeEntry.objects.filter(
        user=current_user,
        timer_type='shift',
        start_time__gte=first_day_of_month,
        start_time__lt=last_day_of_month,
        end_time__isnull=False
    ).aggregate(
        total_hours=Sum(
            (F('end_time') - F('start_time')),
            output_field=models.DurationField()
        )
    )['total_hours']
    total_shift_hours = total_shift_hours.total_seconds() / 3600 if total_shift_hours else 0

    # Аннотируем средний рейтинг и количество завершенных задач
    completed_tasks_subquery = TaskReview.objects.filter(
        user=current_user,
        task__completed=True,
        task__created_at__gte=first_day_of_month,
        task__created_at__lt=last_day_of_month
    ).values('user').annotate(
        count=Count('task')
    ).values('count')

    user = CustomUser.objects.filter(id=current_user.id).annotate(
        average_ratings=Avg('reviews_user__rating', filter=models.Q(reviews_user__rating__isnull=False)),
        completed_tasks_count=Subquery(completed_tasks_subquery, output_field=models.IntegerField())
    ).first()

    worked_photos = Task.objects.filter(
        submitted_by=current_user,
        completed=True,
        created_at__gte=first_day_of_month,
        created_at__lt=last_day_of_month
    ).distinct().count()

    # Рассчитываем общую зарплату сотрудника за выбранный период
    if first_day_of_month and last_day_of_month:
        try:
            # Используем метод total_salary_for_each_user для расчета зарплаты
            individual_salaries = TimeEntry.total_salary_for_each_user_user(
                start_date=first_day_of_month,
                end_date=last_day_of_month
            )
            total_salary = individual_salaries.get(current_user.id, 0)  # Берем зарплату текущего пользователя
        except Exception as e:
            total_salary = 0
    else:
        total_salary = None  # Если период не выбран

    # Передаем данные в шаблон
    context = {
        'user': user,
        'total_salary': total_salary,
        'worked_photos': worked_photos,
        'selected_month': selected_month,
        'current_year': timezone.now().year,
        'current_month': timezone.now().month,
        'start_date': first_day_of_month,
        'total_shift_hours': total_shift_hours,
    }
    return render(request, 'users/statistic.html', context)

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


def photo_maket(request):
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

    # Получаем активную задачу пользователя
    active_task = Task.objects.filter(
        submitted_by=request.user,
        is_rated=False,
        is_submitted_for_review=False
    ).first()

    # Получаем все задачи, на которые назначен пользователь
    assigned_tasks = Task.objects.filter(
        assigned_user=request.user,
        completed=False
    ).select_related('photo')

    # Если у пользователя нет назначенных задач, показываем предупреждение
    if not assigned_tasks.exists() and not active_task:
        messages.warning(request, "У вас нет назначенных задач. Пожалуйста, обратитесь к руководителю.")
    else:
        # Показываем информацию о назначенных задачах
        for task in assigned_tasks:
            messages.info(
                request,
                f'Вы назначены на задачу "{task.title}" в макете "{task.photo.image_name}". '
                f'<a href="/maket_info/{task.photo.id}/" class="task-link">Перейти к макету</a>'
            )

    # Логика отображения макетов
    photos = Photo.objects.prefetch_related('tasks').all()
    for photo in photos:
        total_tasks = Task.objects.filter(photo=photo).count()
        completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

        if total_tasks > 0:
            photo.completion_percentage = (completed_tasks_count / total_tasks) * 100
        else:
            photo.completion_percentage = 0

        # Проверяем, есть ли у пользователя активная задача для этого макета
        photo.has_active_task = active_task and active_task.photo_id == photo.id

    tasks = Task.objects.all()
    return render(request, 'users/photo_maket.html', {
        'photos': photos, 
        'tasks': tasks,
        'active_task': active_task
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
        return redirect('startapp')  # Перенаправляем на страницу начала смены

    # Получаем объект макета по его ID
    photo = get_object_or_404(Photo, id=photo_id)

    total_tasks = Task.objects.filter(photo=photo).count()
    completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()

    if total_tasks > 0:
        photo.completion_percentage = (completed_tasks_count / total_tasks) * 100
    else:
        photo.completion_percentage = 0

    tasks = Task.objects.filter(photo=photo)

    context = {
        'photo': photo,
        'tasks': tasks,
    }
    return render(request, 'users/maket_info.html', context)


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
def check_active_timer(request):
    if request.user.is_authenticated:
        active_entry = TimeEntry.objects.filter(
            user=request.user,
            timer_type='shift',
            end_time__isnull=True
        ).first()
        if active_entry:
            elapsed_time = (timezone.now() - active_entry.start_time).total_seconds()
            return JsonResponse({
                'active': True,
                'elapsed_time': elapsed_time
            })
    return JsonResponse({'active': False})

@csrf_exempt
def api_start_timer(request):
    if request.method == 'POST' and request.user.is_authenticated:
        TimeEntry.objects.create(
            user=request.user,
            timer_type='shift',
            start_time=timezone.now()
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@csrf_exempt
def api_stop_timer(request):
    if request.method == 'POST' and request.user.is_authenticated:
        active_entry = TimeEntry.objects.filter(
            user=request.user,
            timer_type='shift',
            end_time__isnull=True
        ).first()
        if active_entry:
            active_entry.end_time = timezone.now()
            active_entry.save()
            return JsonResponse({'status': 'success'})
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
    return render(request, 'users/my_maket.html', {
        'photos': completed_photos,
        'selected_month': selected_month,
        'current_year': timezone.now().year,
        'current_month': timezone.now().month,
        'start_date': first_day_of_month,
    })

def complete_maket(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    return render(request, 'users/complete_maket.html', {'photo':photo})