from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import logging
from users.models import CustomUser
from manager2.models import Photo, Task
from ..forms import PhotoForm, AddDescriptionForm, UploadFileForm

logger = logging.getLogger('director')

@login_required
def edit_maket(request, id):
    """Редактирование макета"""
    photo = get_object_or_404(Photo, id=id)
    logger.info(f'Пользователь {request.user} начал редактирование макета {photo.id}')
    
    if request.method == 'POST':
        form = PhotoForm(request.POST, request.FILES, instance=photo)
        if form.is_valid():
            form.save()
            logger.info(f'Макет {photo.id} успешно отредактирован пользователем {request.user}')
            return redirect('task_list_director')
        else:
            logger.warning(f'Ошибка валидации формы редактирования макета {photo.id}: {form.errors}')
    else:
        form = PhotoForm(instance=photo)

    return render(request, 'director/edit_maket.html', {'form': form, 'photo': photo})

@login_required
def maket_info_director(request, photo_id):
    """Просмотр информации о макете"""
    photo = get_object_or_404(Photo, id=photo_id)
    logger.info(f'Пользователь {request.user} просматривает информацию о макете {photo_id}')
    return render(request, 'director/maket_info_director.html', {'photo': photo})

@login_required
def add_description(request, photo_id):
    """Добавление описания к макету"""
    photo = get_object_or_404(Photo, id=photo_id)
    logger.info(f'Пользователь {request.user} добавляет описание к макету {photo_id}')

    if request.method == 'POST':
        form = AddDescriptionForm(request.POST)
        if form.is_valid():
            photo.description = form.cleaned_data['description']
            photo.save()
            logger.info(f'Описание к макету {photo_id} успешно добавлено')
            return redirect('task_list_director')
        else:
            logger.warning(f'Ошибка валидации формы добавления описания: {form.errors}')
    else:
        form = AddDescriptionForm()

    return render(request, 'director/add_description.html', {'form': form, 'photo': photo})

@login_required
def delete_photo(request, photo_id):
    """Удаление макета"""
    photo = get_object_or_404(Photo, id=photo_id)
    logger.info(f'Пользователь {request.user} пытается удалить макет {photo_id}')

    if request.method == 'POST':
        if not request.user.is_superuser:
            logger.warning(f'Пользователь {request.user} не имеет прав для удаления макета {photo_id}')
            messages.error(request, 'Недостаточно прав для удаления')
            return redirect('task_list_director')

        Task.objects.filter(photo=photo).delete()
        if photo.image:
            photo.image.delete(save=False)
        photo.delete()
        logger.info(f'Макет {photo_id} успешно удален')
        messages.success(request, 'Макет удален')
        return redirect('task_list_director')

    return redirect('task_list_director')

@login_required
def upload_photo_director(request):
    """Загрузка нового макета"""
    logger.info(f'Пользователь {request.user} начал загрузку нового макета')
    
    if request.method == 'POST':
        photos = request.FILES.getlist('photo')
        form = AddDescriptionForm(request.POST)
        if form.is_valid():
            for photo in photos:
                new_photo = Photo(
                    image=photo,
                    image_name=form.cleaned_data['image_name'],
                    description=form.cleaned_data['description'],
                    requirements=form.cleaned_data['requirements'],
                    due_date=form.cleaned_data['due_date'],
                    assigned_manager=form.cleaned_data['assigned_manager'],
                )
                new_photo.save()
                logger.info(f'Новый макет {new_photo.id} успешно загружен')
            return redirect('task_list_director')
        else:
            logger.warning(f'Ошибка валидации формы загрузки макета: {form.errors}')
            return render(request, 'director/upload_photo_director.html', {'form': form})
    else:
        form = AddDescriptionForm()
    return render(request, 'director/upload_photo_director.html', {'form': form})

@login_required
def photo_report(request):
    """Отчет по фотографиям сотрудников"""
    logger.info(f'Пользователь {request.user} запросил отчет по фотографиям')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    post_user = request.GET.get('post_user')
    sort_by = request.GET.get('sort_by', 'desc')

    try:
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
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
                completed_photos=Count('task__photo',
                                    filter=Q(task__photo__completed=True,
                                           task__photo__created_at__gte=start_date,
                                           task__photo__created_at__lt=end_date_plus_one)),
                average_rating=Avg('task__photo__rating',
                                 filter=Q(task__photo__completed=True,
                                        task__photo__created_at__gte=start_date,
                                        task__photo__created_at__lt=end_date_plus_one))
            )
            total_photos = Photo.objects.filter(completed=True,
                                              created_at__gte=start_date,
                                              created_at__lt=end_date_plus_one).count()
            individual_photos = Photo.objects.filter(completed=True,
                                                  created_at__gte=start_date,
                                                  created_at__lt=end_date_plus_one).values('user__full_name').annotate(
                count=Count('id')
            )
            logger.info(f'Отчет по фотографиям успешно сформирован: {total_photos} фотографий')
        except ValueError as e:
            logger.error(f'Ошибка при формировании отчета: {str(e)}')
            total_photos = 0
            individual_photos = {}
    else:
        total_photos = None
        individual_photos = {}

    users = users.exclude(post_user='manager')

    if post_user:
        users = users.filter(post_user=post_user)

    if sort_by == 'asc':
        users = users.order_by('completed_photos')
    elif sort_by == 'desc':
        users = users.order_by('-completed_photos')
    elif sort_by == 'wasc':
        users = users.order_by('average_rating')
    elif sort_by == 'wdesc':
        users = users.order_by('-average_rating')

    context = {
        'users': users,
        'total_photos': total_photos,
        'individual_photos': individual_photos,
        'post_user_choices': CustomUser.USER_TYPE_CHOICES,
        'selected_post_user': post_user,
        'sort_by': sort_by,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
    }
    return render(request, 'director/photo_report.html', context)

@login_required
def photo_manager(request):
    """Отчет по фотографиям менеджеров"""
    logger.info(f'Пользователь {request.user} запросил отчет по фотографиям менеджеров')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    post_user = request.GET.get('post_user')
    sort_by = request.GET.get('sort_by', 'desc')

    try:
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
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
                created_photos=Count('task__photo',
                                   filter=Q(task__photo__created_at__gte=start_date,
                                          task__photo__created_at__lt=end_date_plus_one)),
                completed_photos=Count('task__photo',
                                     filter=Q(task__photo__completed=True,
                                            task__photo__created_at__gte=start_date,
                                            task__photo__created_at__lt=end_date_plus_one))
            )
            total_photos = Photo.objects.filter(created_at__gte=start_date,
                                              created_at__lt=end_date_plus_one).count()
            individual_photos = Photo.objects.filter(created_at__gte=start_date,
                                                  created_at__lt=end_date_plus_one).values('user__full_name').annotate(
                count=Count('id')
            )
            logger.info(f'Отчет по фотографиям менеджеров успешно сформирован: {total_photos} фотографий')
        except ValueError as e:
            logger.error(f'Ошибка при формировании отчета менеджеров: {str(e)}')
            total_photos = 0
            individual_photos = {}
    else:
        total_photos = None
        individual_photos = {}

    if post_user:
        users = users.filter(post_user=post_user)

    if sort_by == 'asc':
        users = users.order_by('created_photos')
    elif sort_by == 'desc':
        users = users.order_by('-created_photos')
    elif sort_by == 'wasc':
        users = users.order_by('completed_photos')
    elif sort_by == 'wdesc':
        users = users.order_by('-completed_photos')

    context = {
        'users': users,
        'total_photos': total_photos,
        'individual_photos': individual_photos,
        'post_user_choices': CustomUser.USER_TYPE_CHOICES,
        'selected_post_user': post_user,
        'sort_by': sort_by,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
    }

    return render(request, 'director/photo_manager.html', context) 