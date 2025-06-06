from django.contrib import admin

from .models import Task  # Замените YourModel на вашу модель
admin.site.register(Task)