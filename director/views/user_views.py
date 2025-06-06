from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
import logging
from users.models import CustomUser, PromotionRequest
from .forms import UserForm

logger = logging.getLogger('director')

@login_required
def employee_director(request):
    """Список сотрудников (кроме менеджеров)"""
    logger.info(f'Пользователь {request.user} просматривает список сотрудников')
    users = CustomUser.objects.exclude(Q(post_user='manager') | Q(post_user='unapproved'))
    return render(request, 'director/employee.html', {'users': users})

@login_required
def employee_manager(request):
    """Список менеджеров"""
    logger.info(f'Пользователь {request.user} просматривает список менеджеров')
    users = CustomUser.objects.filter(post_user='manager')
    return render(request, 'director/employee_manager.html', {'users': users})

@login_required
def profile_employee(request, user_id):
    """Профиль сотрудника"""
    user = get_object_or_404(CustomUser, id=user_id)
    logger.info(f'Пользователь {request.user} просматривает профиль сотрудника {user.full_name}')
    return render(request, 'director/profile_employee.html', {'user': user})

@login_required
def edit_user(request, user_id):
    """Редактирование пользователя"""
    user = get_object_or_404(CustomUser, id=user_id)
    logger.info(f'Пользователь {request.user} редактирует профиль сотрудника {user.full_name}')
    
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            post_user = form.cleaned_data.get('post_user')
            if post_user != user.post_user:
                user.big_stavka = user.calculate_default_stavka()
                logger.info(f'Изменена должность пользователя {user.full_name} с {user.post_user} на {post_user}')
            else:
                user.big_stavka = form.cleaned_data.get('big_stavka', user.big_stavka)
            form.save()
            logger.info(f'Профиль пользователя {user.full_name} успешно обновлен')
            return redirect('/director/employee_director/')
        else:
            logger.warning(f'Ошибка валидации формы редактирования пользователя: {form.errors}')
    else:
        form = UserForm(instance=user)
    return render(request, 'director/edit_user.html', {'form': form, 'user': user})

@login_required
def director_promotions(request):
    """Управление запросами на повышение"""
    logger.info(f'Пользователь {request.user} просматривает запросы на повышение')
    promotion_requests = PromotionRequest.objects.all()

    if request.method == 'POST':
        promotion_request_id = request.POST.get('promotion_request_id')
        approve = request.POST.get('approve')

        try:
            promotion_request = PromotionRequest.objects.get(id=promotion_request_id)
            if approve:
                user = promotion_request.user
                user.post_user = promotion_request.requested_post
                user.save()
                logger.info(f'Запрос на повышение пользователя {user.full_name} подтвержден')
                messages.success(request, 'Запрос на повышение подтвержден и должность обновлена.')
            else:
                logger.info(f'Запрос на повышение пользователя {promotion_request.user.full_name} отклонен')
                messages.info(request, 'Запрос на повышение отклонен.')

            promotion_request.delete()

        except PromotionRequest.DoesNotExist:
            logger.error(f'Запрос на повышение {promotion_request_id} не найден')
            messages.error(request, 'Запрос на повышение не найден.')
        except Exception as e:
            logger.error(f'Ошибка при обработке запроса на повышение: {str(e)}')
            messages.error(request, f'Ошибка: {str(e)}')

    return render(request, 'director/director_promotions.html', {
        'promotion_requests': promotion_requests
    })

@login_required
def director_dashboard(request):
    """Панель управления директора"""
    logger.info(f'Пользователь {request.user} открыл панель управления директора')
    unapproved_users = CustomUser.objects.filter(post_user='unapproved', is_active=True)
    user_type_choices = CustomUser.USER_TYPE_CHOICES

    return render(request, 'director/director_dashboard.html', {
        'unapproved_users': unapproved_users,
        'user_type_choices': user_type_choices,
    })

@login_required
def approve_user(request, user_id):
    """Подтверждение пользователя"""
    user = get_object_or_404(CustomUser, id=user_id)
    user_role = request.POST.get('user_role')
    if user_role:
        user.post_user = user_role
        user.save()
        logger.info(f'Пользователь {user.email} подтвержден как {user_role}')
        messages.success(request, f'Пользователь {user.email} был подтверждён как {user_role}.')
    return redirect('director_dashboard') 