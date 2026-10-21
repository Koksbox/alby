"""Verified, generation-scoped storage. No provider ever deletes source files."""
import hashlib
import json
import os
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone

from .models import BackupConnection
from .tokens import decrypt_token, save_connection_tokens


class BackupError(RuntimeError):
    pass


def generation_id(value):
    value = str(value)
    if str(uuid.UUID(value)) != value:
        raise BackupError('Invalid backup generation identifier.')
    return value


def file_hashes(path):
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            sha256.update(block)
            md5.update(block)
    return {'sha256': sha256.hexdigest(), 'md5': md5.hexdigest(), 'size': Path(path).stat().st_size}


def archive_name(value):
    if not isinstance(value, str) or Path(value).name != value or not value.startswith('alby_') or not value.endswith('.zip'):
        raise BackupError('Invalid backup archive name.')
    return value


def safe_directory(root, generation):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / generation_id(generation)
    if target.is_symlink():
        raise BackupError('Backup generation cannot be a symbolic link.')
    return target


class LocalStorage:
    def __init__(self):
        self.root = Path(settings.BACKUP_LOCAL_ROOT).resolve()

    def store(self, run, stage):
        target = safe_directory(self.root, run.id)
        target.mkdir(mode=0o700, exist_ok=True)
        marker = target / 'manifest.json'
        if marker.is_symlink():
            raise BackupError('Backup manifest cannot be a symbolic link.')
        if marker.exists():
            try:
                if not marker.is_file() or json.loads(marker.read_text(encoding='utf8')) != run.manifest:
                    raise ValueError()
            except (ValueError, OSError):
                raise BackupError('Refusing to replace a published local backup with a different snapshot.') from None
        for entry in run.manifest['archives']:
            name = archive_name(entry['name'])
            destination = target / name
            if destination.is_symlink():
                raise BackupError('Backup file cannot be a symbolic link.')
            if destination.exists() and file_hashes(destination) == self._expected(entry):
                continue
            partial = target / (name + '.part')
            if partial.is_symlink():
                raise BackupError('Partial backup cannot be a symbolic link.')
            with (Path(stage) / name).open('rb') as source, partial.open('wb') as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            if file_hashes(partial) != self._expected(entry):
                raise BackupError('Local backup checksum mismatch.')
            os.replace(partial, destination)
        if marker.is_symlink() or (target / 'manifest.json.part').is_symlink():
            raise BackupError('Backup manifest cannot be a symbolic link.')
        temporary = target / 'manifest.json.part'
        with temporary.open('w', encoding='utf8') as handle:
            json.dump(run.manifest, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, marker)
        # Re-read the marker and verify files after publication.
        if json.loads(marker.read_text()) != run.manifest:
            raise BackupError('Local backup manifest mismatch.')

    @staticmethod
    def _expected(entry):
        return {key: entry[key] for key in ('sha256', 'md5', 'size')}

    def delete(self, run):
        target = safe_directory(self.root, run.id)
        if not target.exists():
            return
        # A crash after removing the marker but before rmdir leaves only this
        # empty, known UUID directory. Finishing rmdir cannot delete foreign files.
        if not any(target.iterdir()):
            target.rmdir()
            return
        marker = target / 'manifest.json'
        if marker.is_symlink() or not marker.is_file():
            raise BackupError('Refusing to delete an unrecognized local backup.')
        manifest = json.loads(marker.read_text())
        if manifest.get('generation') != str(run.id) or manifest != run.manifest:
            raise BackupError('Refusing to delete an unrecognized local backup.')
        expected = {'manifest.json'} | {archive_name(a['name']) for a in run.manifest['archives']}
        if any(p.is_symlink() or p.name not in expected for p in target.iterdir()):
            raise BackupError('Unexpected file in backup directory; cleanup refused.')
        # The marker is removed last so interrupted cleanup remains retryable.
        for name in sorted(expected - {'manifest.json'}):
            (target / name).unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        target.rmdir()


class YandexStorage:
    API = 'https://cloud-api.yandex.net/v1/disk'

    def __init__(self):
        self.root = getattr(settings, 'YANDEX_BACKUP_ROOT', 'app:/AlbyBackups').rstrip('/')
        if not self.root.startswith(('app:/', 'disk:/')) or '..' in self.root.split('/'):
            raise BackupError('Invalid YANDEX_BACKUP_ROOT.')
        self.connection = BackupConnection.objects.filter(pk=1).first()
        if not self.connection or not self.connection.is_connected:
            token = getattr(settings, 'YANDEX_ACCESS_TOKEN', '')
            if not token:
                raise BackupError('Yandex Disk is not connected.')
            self.connection = save_connection_tokens({
                'access_token': token,
                'refresh_token': getattr(settings, 'YANDEX_REFRESH_TOKEN', ''),
            })
        self.session = requests.Session()
        if self.connection.expires_at and self.connection.expires_at < timezone.now() + timedelta(minutes=2):
            self._refresh()

    def _refresh(self):
        refresh_token = decrypt_token(self.connection.refresh_token_encrypted)
        if not refresh_token:
            raise BackupError('Yandex authorization expired; reconnect the Disk.')
        try:
            response = self.session.post('https://oauth.yandex.ru/token', data={
                'grant_type': 'refresh_token', 'refresh_token': refresh_token,
                'client_id': settings.YANDEX_CLIENT_ID, 'client_secret': settings.YANDEX_CLIENT_SECRET,
            }, timeout=(10, 60))
        except requests.RequestException:
            raise BackupError('Yandex token refresh connection failed.') from None
        if response.status_code != 200:
            raise BackupError('Yandex authorization must be renewed.')
        try:
            payload = response.json()
            if not payload.get('access_token'):
                raise ValueError()
            self.connection = save_connection_tokens(payload, connection=self.connection)
        except (ValueError, KeyError, TypeError):
            raise BackupError('Invalid Yandex token response.') from None

    def _request(self, method, endpoint, allow=(200,), refresh=True, **kwargs):
        token = decrypt_token(self.connection.access_token_encrypted)
        try:
            response = self.session.request(method, self.API + endpoint,
                headers={'Authorization': 'OAuth ' + token}, timeout=(10, 120), **kwargs)
        except requests.RequestException:
            raise BackupError('Yandex Disk connection failed.') from None
        if response.status_code == 401 and refresh:
            self._refresh()
            return self._request(method, endpoint, allow, refresh=False, **kwargs)
        if response.status_code not in allow:
            raise BackupError('Yandex Disk request failed (HTTP %s).' % response.status_code)
        return response

    def _mkdir(self, path):
        # Create only ancestors within the configured application/disk namespace.
        namespace, suffix = path.split(':/', 1)
        current = namespace + ':/'
        for component in suffix.split('/'):
            if not component:
                continue
            current = current.rstrip('/') + '/' + component
            response = self._request('PUT', '/resources', allow=(201, 409), params={'path': current})
            if response.status_code == 409:
                meta = self._metadata(current)
                if not meta or meta.get('type') != 'dir':
                    raise BackupError('Yandex backup path is not a directory.')

    def _metadata(self, path):
        response = self._request('GET', '/resources', allow=(200, 404), params={'path': path})
        if response.status_code == 404:
            return None
        try:
            return response.json()
        except ValueError:
            raise BackupError('Invalid Yandex metadata response.') from None

    @staticmethod
    def _matches(meta, entry):
        if not meta or meta.get('type') != 'file' or meta.get('size') != entry['size']:
            return False
        if meta.get('sha256'):
            return meta['sha256'].lower() == entry['sha256']
        return bool(meta.get('md5')) and meta['md5'].lower() == entry['md5']

    def _upload(self, source, path, expected):
        if self._matches(self._metadata(path), expected):
            return
        response = self._request('GET', '/resources/upload', params={'path': path, 'overwrite': 'true'})
        try:
            href = response.json()['href']
            parsed = urlparse(href)
            if parsed.scheme != 'https' or not parsed.hostname or not any(
                parsed.hostname.endswith('.' + host) for host in ('yandex.net', 'yandex.ru', 'yandex.com')
            ):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise BackupError('Invalid Yandex upload address.') from None
        try:
            with Path(source).open('rb') as handle:
                uploaded = self.session.put(href, data=handle, timeout=(10, 120))
        except requests.RequestException:
            raise BackupError('Yandex upload interrupted.') from None
        if uploaded.status_code not in (201, 202):
            raise BackupError('Yandex upload failed (HTTP %s).' % uploaded.status_code)
        for attempt in range(10):
            if self._matches(self._metadata(path), expected):
                return
            time.sleep(1)
        raise BackupError('Yandex uploaded file checksum was not confirmed.')

    def store(self, run, stage):
        generation = generation_id(run.id)
        target = self.root + '/' + generation
        # A completion marker makes the generation immutable. This guard also
        # protects existing backups if an older database snapshot is restored
        # with a RUNNING job whose original manifest had not yet been saved.
        marker = Path(stage) / 'manifest.json'
        if marker.is_symlink():
            raise BackupError('Backup staging manifest cannot be a symbolic link.')
        marker.write_text(json.dumps(run.manifest, ensure_ascii=False, sort_keys=True), encoding='utf8')
        marker_hashes = file_hashes(marker)
        published = self._metadata(target + '/manifest.json')
        if published is not None and not self._matches(published, marker_hashes):
            raise BackupError('Refusing to replace a published Yandex backup with a different snapshot.')
        self._mkdir(target)
        for entry in run.manifest['archives']:
            name = archive_name(entry['name'])
            self._upload(Path(stage) / name, target + '/' + name, entry)
        self._upload(marker, target + '/manifest.json', marker_hashes)

    def delete(self, run):
        target = self.root + '/' + generation_id(run.id)
        meta = self._metadata(target)
        if meta is None:
            return
        expected = {'manifest.json'} | {archive_name(a['name']) for a in run.manifest['archives']}
        embedded = meta.get('_embedded', {})
        items = embedded.get('items', [])
        if embedded.get('total') != len(expected) or {item.get('name') for item in items} != expected or any(item.get('type') != 'file' for item in items):
            raise BackupError('Unexpected file in Yandex backup directory; cleanup refused.')
        # Read the completion manifest and check ownership/content before deleting.
        response = self._request('GET', '/resources/download', params={'path': target + '/manifest.json'})
        try:
            href = response.json()['href']
            parsed = urlparse(href)
            if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith(('.yandex.net', '.yandex.ru', '.yandex.com')):
                raise ValueError()
            downloaded = self.session.get(href, timeout=(10, 60))
            if downloaded.status_code != 200 or downloaded.json() != run.manifest:
                raise ValueError()
        except (ValueError, KeyError, TypeError, requests.RequestException):
            raise BackupError('Refusing to delete an unrecognized Yandex backup.') from None
        self._request('DELETE', '/resources', allow=(204, 202, 404), params={'path': target, 'permanently': 'true'})
        for attempt in range(10):
            if self._metadata(target) is None:
                return
            time.sleep(1)
        raise BackupError('Yandex backup deletion is still pending.')
