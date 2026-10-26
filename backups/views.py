"""Director-only connection and status. Backup execution stays in the worker."""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from .models import BackupConnection, BackupRun, BackupSchedule
from .permissions import backup_director_required
from .tokens import save_connection_tokens


def connection_status():
    connection = BackupConnection.objects.filter(pk=1).first()
    schedule = BackupSchedule.objects.filter(pk=1).first()
    last_run = BackupRun.objects.order_by('-created_at').first()
    detached = bool(connection and connection.disconnected_at is not None)
    connected = not detached and bool((connection and connection.is_connected) or settings.YANDEX_ACCESS_TOKEN)
    state = 'connected' if connected else 'disconnected'
    if last_run and last_run.status == BackupRun.Status.FAILED:
        state = 'error'
    elif last_run and last_run.status == BackupRun.Status.RUNNING:
        state = 'running'
    return {
        'connected': connected, 'state': state,
        'enabled': settings.BACKUP_ENABLED,
        'cleanup_pending': bool(last_run and last_run.cleanup_pending),
        'last_success_at': schedule.last_success_at if schedule else None,
        'next_run_at': schedule.next_run_at if schedule else None,
    }


@login_required
@backup_director_required
@require_GET
def status(request):
    return JsonResponse(connection_status())


@login_required
@backup_director_required
@require_GET
def yandex_connect(request):
    if not all((settings.YANDEX_CLIENT_ID, settings.YANDEX_CLIENT_SECRET,
                settings.YANDEX_REDIRECT_URI, settings.BACKUP_ENCRYPTION_KEY)):
        messages.error(request, 'Для подключения Яндекс Диска заполните настройки в .env.')
        return redirect('home_director')
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    request.session['yandex_backup_oauth'] = {'state': state, 'verifier': verifier, 'created': time.time()}
    params = {
        'response_type': 'code', 'client_id': settings.YANDEX_CLIENT_ID,
        'redirect_uri': settings.YANDEX_REDIRECT_URI,
        'scope': settings.YANDEX_OAUTH_SCOPE, 'state': state, 'force_confirm': 'yes',
        'code_challenge': challenge, 'code_challenge_method': 'S256',
    }
    return redirect('https://oauth.yandex.ru/authorize?' + urlencode(params))


@login_required
@backup_director_required
@require_GET
def yandex_callback(request):
    pending = request.session.pop('yandex_backup_oauth', None)
    state = request.GET.get('state', '')
    if (not pending or not state or not secrets.compare_digest(state, pending['state'])
            or time.time() - pending['created'] > 600):
        messages.error(request, 'Подключение не подтверждено. Повторите подключение Яндекс Диска.')
        return redirect('home_director')
    code = request.GET.get('code')
    if not code or request.GET.get('error'):
        messages.error(request, 'Яндекс Диск не подключён: доступ не предоставлен.')
        return redirect('home_director')
    try:
        response = requests.post('https://oauth.yandex.ru/token', data={
            'grant_type': 'authorization_code', 'code': code,
            'client_id': settings.YANDEX_CLIENT_ID, 'client_secret': settings.YANDEX_CLIENT_SECRET,
            'code_verifier': pending['verifier'],
        }, timeout=(10, 30))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get('access_token'), str) or not payload['access_token']:
            raise ValueError('Missing access token')
        save_connection_tokens(payload)
    except (requests.RequestException, ValueError, KeyError, ImproperlyConfigured):
        messages.error(request, 'Не удалось подключить Яндекс Диск. Проверьте настройки приложения и повторите попытку.')
        return redirect('home_director')
    messages.success(request, 'Яндекс Диск подключён.')
    return redirect('home_director')
