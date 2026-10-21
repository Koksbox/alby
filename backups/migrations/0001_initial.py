import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='BackupConnection', fields=[
            ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
            ('access_token_encrypted', models.TextField(blank=True)),
            ('refresh_token_encrypted', models.TextField(blank=True)),
            ('expires_at', models.DateTimeField(blank=True, null=True)),
            ('connected_at', models.DateTimeField(blank=True, null=True)),
            ('account_name', models.CharField(blank=True, max_length=255)),
        ]),
        migrations.CreateModel(name='BackupSchedule', fields=[
            ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
            ('next_run_at', models.DateTimeField(blank=True, null=True)),
            ('last_success_at', models.DateTimeField(blank=True, null=True)),
        ]),
        migrations.CreateModel(name='BackupRun', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('status', models.CharField(choices=[('pending', 'Ожидает'), ('running', 'Выполняется'), ('failed', 'Ошибка'), ('succeeded', 'Сохранено')], default='pending', max_length=12)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('started_at', models.DateTimeField(blank=True, null=True)),
            ('completed_at', models.DateTimeField(blank=True, null=True)),
            ('retry_at', models.DateTimeField(blank=True, null=True)),
            ('error', models.TextField(blank=True)),
            ('manifest', models.JSONField(blank=True, default=dict)),
            ('local_verified', models.BooleanField(default=False)),
            ('yandex_verified', models.BooleanField(default=False)),
            ('cleanup_pending', models.BooleanField(default=False)),
        ], options={'ordering': ['-created_at'], 'permissions': [('manage_backups', 'Can manage company backup connection and status')]}),
    ]
