import uuid

from django.db import models


class BackupConnection(models.Model):
    """One company Disk connection. Tokens are encrypted by backups.tokens."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    access_token_encrypted = models.TextField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)
    account_name = models.CharField(max_length=255, blank=True)

    @property
    def is_connected(self):
        return bool(self.access_token_encrypted) and self.disconnected_at is None


class BackupSchedule(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)


class BackupRun(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        RUNNING = 'running', 'Выполняется'
        FAILED = 'failed', 'Ошибка'
        SUCCEEDED = 'succeeded', 'Сохранено'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    retry_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    manifest = models.JSONField(default=dict, blank=True)
    local_verified = models.BooleanField(default=False)
    yandex_verified = models.BooleanField(default=False)
    cleanup_pending = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        permissions = [('manage_backups', 'Can manage company backup connection and status')]
