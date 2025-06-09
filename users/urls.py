from tkinter.font import names
from django.contrib import admin
from django.urls import path, include
from . import views
from .views import UserPostDetail


urlpatterns = [
    path('sw.js', views.ServiceWorkerView.as_view(), name=views.ServiceWorkerView.name),
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('post/', views.select_user_type, name='post'),
    path('director/', include('director.urls')),
    path('confirm/', views.confirm_registration, name='confirm'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('password/', views.password_reset_request, name='password'),
    path('new_password/', views.password_reset_code, name='new_password'),
    path('refactor_profile/', views.refactor_profile, name='refactor_profile'),
    path('startapp/', views.startapp, name='startapp'),
    path('manager/', include('manager2.urls')),
    path('now_user', views.now_user, name='now_user'),
    path('api/', UserPostDetail.as_view(), name='user_post_detail'),
    path('completed_task_user', views.completed_task_user, name='completed_task_user'),
    path('select_task/<int:photo_id>/', views.select_task, name='select_task'),
    path('work_on_task/<int:task_id>/', views.work_on_task, name='work_on_task'),
    path('task/<int:task_id>/start/', views.start_timer, name='start_timer'),
    path('task/<int:task_id>/stop/', views.stop_timer, name='stop_timer'),
    path('start-timer/', views.start_timer1, name='start_timer1'),
    path('stop-timer/', views.stop_timer1, name='stop_timer1'),
    path('money/', views.money, name='money'),
    path('users_prize/', views.users_prize, name='users_prize'),
    path('statistic/', views.user_statistic, name='statistic'),
    path('upload-avatar_users/', views.upload_avatar_users, name='upload_avatar_users'),
    path('photo_maket/', views.photo_maket, name='photo_maket'),
    path('maket_info/<int:photo_id>/', views.maket_info, name='maket_info'),
    path('toggle-timer/', views.toggle_timer, name='toggle_timer'),
    path('zadachi/', views.zadachi, name='zadachi'),
    path('api/check-active-timer/', views.check_active_timer, name='check_active_timer'),
    path('api/start-timer/', views.api_start_timer, name='api_start_timer'),
    path('api/stop-timer/', views.api_stop_timer, name='api_stop_timer'),
    path('my_maket', views.my_maket, name='my_maket'),
    path('complete_maket/<int:photo_id>/', views.complete_maket, name='complete_maket'),
    path('task_history/', views.task_history, name='task_history'),
]
