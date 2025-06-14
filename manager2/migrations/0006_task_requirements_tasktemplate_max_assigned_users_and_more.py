# Generated by Django 5.1.4 on 2025-06-04 16:56

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manager2', '0005_alter_photo_options_alter_photofile_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='requirements',
            field=models.TextField(blank=True, null=True, verbose_name='Требования'),
        ),
        migrations.AddField(
            model_name='tasktemplate',
            name='max_assigned_users',
            field=models.PositiveIntegerField(default=1, verbose_name='Максимальное количество сотрудников'),
        ),
        migrations.AddField(
            model_name='tasktemplate',
            name='requirements',
            field=models.TextField(blank=True, verbose_name='Требования'),
        ),
        migrations.AlterField(
            model_name='task',
            name='max_assigned_users',
            field=models.PositiveIntegerField(default=1, verbose_name='Максимальное количество сотрудников'),
        ),
        migrations.AlterField(
            model_name='tasktemplate',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Создал'),
        ),
        migrations.AlterField(
            model_name='tasktemplate',
            name='title',
            field=models.CharField(max_length=200, verbose_name='Название шаблона'),
        ),
    ]
