from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import logging
from users.models import CustomUser
from manager2.models import Task, Photo, TaskReview
from manager2.forms import TaskForm

logger = logging.getLogger('director')

@login_required
def add_task_director(request, photo_id):
    """Добавление новой задачи к макету"""
    photo = get_object_or_404(Photo, pk=photo_id)
    logger.info(f'Пользователь {request.user} начал добавление задачи к макету {photo_id}')

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.photo = photo
            task.created_by = request.user if request.user.is_authenticated else None
            task.save()

            assigned_users = form.cleaned_data.get('assigned_user', [])
            if assigned_users:
                unique_users = [
                    user for user in assigned_users
                    if user not in task.submitted_by.all()
                ]

                if len(unique_users) > task.max_assigned_users:
                    logger.warning(f'Превышено максимальное количество сотрудников для задачи {task.id}')
                    messages.error(request,
                                f'Превышено максимальное количество сотрудников ({task.max_assigned_users}).')
                    return redirect('add_task_director', photo_id=photo_id)

                task.assigned_user.add(*unique_users)
                logger.info(f'К задаче {task.id} добавлены пользователи: {[user.full_name for user in unique_users]}')

            if task.is_full():
                logger.info(f'Задача {task.id} полностью заполнена')
                messages.warning(request, 'Задача полностью заполнена.')

            return redirect('maket_director', photo_id=photo_id)
        else:
            logger.warning(f'Ошибка валидации формы добавления задачи: {form.errors}')
    else:
        form = TaskForm()

    return render(request, 'director/add_task_director.html', {'form': form, 'photo': photo})

@login_required
def delete_task_director(request, task_id):
    """Удаление задачи"""
    task = get_object_or_404(Task, id=task_id)
    photo_id = task.photo.id
    logger.info(f'Пользователь {request.user} удаляет задачу {task_id}')
    task.delete()
    logger.info(f'Задача {task_id} успешно удалена')
    return redirect('maket_director', photo_id=photo_id)

@login_required
def task_list_director(request):
    """Список задач директора"""
    logger.info(f'Пользователь {request.user} просматривает список задач')
    
    if request.method == "POST":
        action = request.POST.get("action")
        photo_id = request.POST.get("photo_id")

        if action == "complete":
            photo = get_object_or_404(Photo, id=photo_id)
            tasks = Task.objects.filter(photo=photo)
            
            if not all(task.completed for task in tasks):
                logger.warning(f'Попытка завершить макет {photo_id} с незавершенными задачами')
                return render(request, "director/task_list_director.html", {
                    "tasks": Task.objects.all(),
                    "photos": Photo.objects.all(),
                    "error_message": f"Невозможно завершить макет. Сначала завершите все задачи для макета {photo.image_name}."
                })

            if not photo.is_completed:
                photo.is_completed = True
                photo.save()
                logger.info(f'Макет {photo_id} успешно завершен')

            return redirect('task_list_director')

    photos = Photo.objects.all()
    for photo in photos:
        total_tasks = Task.objects.filter(photo=photo).count()
        completed_tasks_count = Task.objects.filter(photo=photo, completed=True).count()
        photo.completion_percentage = (completed_tasks_count / total_tasks) * 100 if total_tasks > 0 else 0
        logger.debug(f'Макет {photo.id}: {photo.completion_percentage}% завершен')

    tasks = Task.objects.all()
    return render(request, "director/task_list_director.html", {
        "tasks": tasks,
        "photos": photos
    }) 