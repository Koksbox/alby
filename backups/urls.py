from django.urls import path
from . import views

app_name = 'backups'
urlpatterns = [
    path('status/', views.status, name='status'),
    path('yandex/connect/', views.yandex_connect, name='yandex_connect'),
    path('yandex/callback/', views.yandex_callback, name='yandex_callback'),
]
