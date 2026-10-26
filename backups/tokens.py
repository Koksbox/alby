from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from .models import BackupConnection


def _fernet():
    key = getattr(settings, 'BACKUP_ENCRYPTION_KEY', '')
    if not key:
        raise ImproperlyConfigured('BACKUP_ENCRYPTION_KEY is required for the Yandex connection.')
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured('BACKUP_ENCRYPTION_KEY must be a Fernet key.') from exc


def encrypt_token(value):
    return _fernet().encrypt(value.encode()).decode() if value else ''


def decrypt_token(value):
    if not value:
        return ''
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ImproperlyConfigured('Cannot decrypt Yandex credentials; check BACKUP_ENCRYPTION_KEY.') from exc


def save_connection_tokens(payload, account_name='', connection=None):
    reconnecting = connection is None
    connection = connection or BackupConnection.objects.get_or_create(pk=1)[0]
    connection.access_token_encrypted = encrypt_token(payload['access_token'])
    if payload.get('refresh_token'):
        connection.refresh_token_encrypted = encrypt_token(payload['refresh_token'])
    expires_in = payload.get('expires_in')
    connection.expires_at = timezone.now() + timedelta(seconds=int(expires_in)) if expires_in else None
    connection.connected_at = connection.connected_at or timezone.now()
    if reconnecting:
        connection.disconnected_at = None
    if account_name:
        connection.account_name = account_name
    connection.save()
    return connection
