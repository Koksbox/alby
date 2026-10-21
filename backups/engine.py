"""Durable backup state machine; invoked only by the background command."""
from datetime import timedelta
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import time
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

from django.conf import settings
from django.db import connection
from django.utils import timezone

from .locking import backup_lock, media_write_lock
from .models import BackupRun, BackupSchedule
from .providers import BackupError, LocalStorage, YandexStorage, archive_name, file_hashes, safe_directory

logger = logging.getLogger(__name__)


class PreparedStageUnavailable(BackupError):
    """The persisted snapshot exists, but its temporary delivery files were lost."""


def configured_roots():
    staging = Path(settings.BACKUP_STAGING_ROOT).resolve()
    local = Path(settings.BACKUP_LOCAL_ROOT).resolve()
    media = Path(settings.MEDIA_ROOT).resolve()
    protected = [media, Path(settings.STATIC_ROOT).resolve(), Path(settings.BASE_DIR).resolve()]
    for root in (staging, local):
        if any(root == source or (source != Path(settings.BASE_DIR).resolve() and source in root.parents) for source in protected):
            raise BackupError('Backup directories must be outside media/static and cannot equal the project root.')
        if root in media.parents:
            raise BackupError('A backup directory cannot contain the source media directory.')
    if staging == local or staging in local.parents or local in staging.parents:
        raise BackupError('Staging and local backup directories must be separate.')
    return staging, local, media


def inventory(media):
    if not media.is_dir():
        raise BackupError('MEDIA_ROOT is missing; refusing to create an empty replacement backup.')
    result = {}
    for directory, dirs, files in os.walk(media, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise BackupError('Media contains a symbolic link; backup requires regular files.')
            if stat.S_ISREG(info.st_mode):
                result[path.relative_to(media).as_posix()] = (info.st_size, info.st_mtime_ns, info.st_ino)
            elif not stat.S_ISDIR(info.st_mode):
                raise BackupError('Media contains a non-regular file.')
    return result


def _sqlite_snapshot(destination):
    connection.ensure_connection()
    name = str(connection.settings_dict['NAME'])
    own_source = False
    if name == ':memory:' or 'mode=memory' in name:
        source = connection.connection
    else:
        uri = name if name.startswith('file:') else Path(name).resolve().as_uri() + '?mode=ro'
        source = sqlite3.connect(uri, uri=True, timeout=10)
        own_source = True
    deadline = time.monotonic() + getattr(settings, 'BACKUP_SNAPSHOT_TIMEOUT', 300)
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise BackupError('Database snapshot timed out.')
    try:
        with sqlite3.connect(destination) as output:
            source.backup(output, pages=256, progress=progress, sleep=0.05)
            if output.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise BackupError('SQLite snapshot integrity check failed.')
    finally:
        if own_source:
            source.close()


def _postgres_snapshot(destination):
    db = connection.settings_dict
    args = [getattr(settings, 'BACKUP_PG_DUMP_BINARY', 'pg_dump'), '--format=custom', '--no-password',
            '--file', str(destination), '--dbname', str(db['NAME'])]
    for setting, option in [('HOST', '--host'), ('PORT', '--port'), ('USER', '--username')]:
        if db.get(setting):
            args += [option, str(db[setting])]
    environment = os.environ.copy()
    if db.get('PASSWORD'):
        environment['PGPASSWORD'] = str(db['PASSWORD'])
    for key, value in db.get('OPTIONS', {}).items():
        envname = {'sslmode': 'PGSSLMODE', 'sslcert': 'PGSSLCERT', 'sslkey': 'PGSSLKEY', 'sslrootcert': 'PGSSLROOTCERT'}.get(key)
        if envname:
            environment[envname] = str(value)
    try:
        subprocess.run(args, check=True, env=environment, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=getattr(settings, 'BACKUP_SNAPSHOT_TIMEOUT', 300))
    except (subprocess.SubprocessError, OSError):
        raise BackupError('PostgreSQL snapshot failed; check pg_dump installation and database access.') from None


def _validated_stage(run, stage):
    if not run.manifest:
        return False
    if run.manifest.get('generation') != str(run.id):
        raise BackupError('Backup manifest belongs to another generation.')
    archives = run.manifest.get('archives', [])
    if len(archives) != 2:
        raise BackupError('Backup manifest must contain the database and media archives.')
    for entry in archives:
        name = entry['name']
        if Path(name).name != name or not name.endswith('.zip'):
            raise BackupError('Invalid backup archive name.')
        path = stage / name
        if path.is_symlink():
            raise BackupError('Prepared backup archive is unsafe.')
        if not path.is_file():
            raise PreparedStageUnavailable('Prepared backup archive is missing.')
        if file_hashes(path) != {k: entry[k] for k in ('sha256', 'md5', 'size')}:
            raise PreparedStageUnavailable('Prepared backup archive checksum mismatch.')
    return True


def recover_staging_from_local(run, stage):
    """Recover the exact saved snapshot; never take a new snapshot under its UUID."""
    source = safe_directory(settings.BACKUP_LOCAL_ROOT, run.id)
    marker = source / 'manifest.json'
    if marker.is_symlink() or not marker.is_file():
        raise BackupError('Prepared archives are unavailable and no verified local copy can recover them.')
    try:
        if json.loads(marker.read_text(encoding='utf8')) != run.manifest:
            raise ValueError()
    except (ValueError, OSError):
        raise BackupError('Local recovery manifest does not match the saved snapshot.') from None
    entries = run.manifest['archives']
    allowed = {'manifest.json'} | {archive_name(entry['name']) for entry in entries}
    allowed |= {archive_name(entry['name']) + '.part' for entry in entries}
    if any(p.is_symlink() or not p.is_file() or p.name not in allowed for p in stage.iterdir()):
        raise BackupError('Unexpected staging contents; recovery refused.')
    # Validate every source archive before changing staging, including archives
    # that might already be intact in staging. A marker alone is not sufficient.
    for entry in entries:
        original = source / archive_name(entry['name'])
        expected = {key: entry[key] for key in ('sha256', 'md5', 'size')}
        if original.is_symlink() or not original.is_file() or file_hashes(original) != expected:
            raise BackupError('Local recovery archive failed checksum verification.')
    for entry in entries:
        name = archive_name(entry['name'])
        partial = stage / (name + '.part')
        with (source / name).open('rb') as original, partial.open('wb') as output:
            shutil.copyfileobj(original, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        if file_hashes(partial) != {key: entry[key] for key in ('sha256', 'md5', 'size')}:
            raise BackupError('Recovered staging archive failed checksum verification.')
        os.replace(partial, stage / name)
    _validated_stage(run, stage)


def prepare(run):
    staging, _, media = configured_roots()
    stage = safe_directory(staging, run.id)
    stage.mkdir(mode=0o700, exist_ok=True)
    try:
        if _validated_stage(run, stage):
            return stage
    except PreparedStageUnavailable:
        recover_staging_from_local(run, stage)
        return stage
    # Only an unfinished generation without a published manifest is rebuilt.
    if any(p.is_symlink() or p.is_dir() for p in stage.iterdir()):
        raise BackupError('Unexpected contents in backup staging directory.')
    for path in stage.iterdir():
        path.unlink()
    date = timezone.localtime(run.created_at).strftime('%Y-%m-%d_%H-%M-%S')
    suffix = str(run.id)[:8]
    db_name = 'alby_db_%s_%s.zip' % (date, suffix)
    media_name = 'alby_media_%s_%s.zip' % (date, suffix)
    try:
        with media_write_lock():
            before = inventory(media)
            vendor = connection.vendor
            database_file = stage / ('database.sqlite3' if vendor == 'sqlite' else 'database.dump')
            if vendor == 'sqlite':
                _sqlite_snapshot(database_file)
            elif vendor == 'postgresql':
                _postgres_snapshot(database_file)
            else:
                raise BackupError('Backup supports SQLite and PostgreSQL databases only.')
            with ZipFile(stage / db_name, 'w', ZIP_DEFLATED, compresslevel=3, allowZip64=True) as archive:
                archive.write(database_file, database_file.name)
            database_file.unlink()
            # Images are already compressed: store media without re-compressing it.
            with ZipFile(stage / media_name, 'w', ZIP_STORED, allowZip64=True) as archive:
                if not before:
                    archive.writestr('media/', '')
                for relative, expected in sorted(before.items()):
                    path = media / relative
                    info = path.lstat()
                    if path.is_symlink() or (info.st_size, info.st_mtime_ns, info.st_ino) != expected:
                        raise BackupError('Media changed while preparing a backup; retry required.')
                    archive.write(path, 'media/' + relative)
                    info = path.lstat()
                    if (info.st_size, info.st_mtime_ns, info.st_ino) != expected:
                        raise BackupError('Media changed while preparing a backup; retry required.')
            if inventory(media) != before:
                raise BackupError('Media changed while preparing a backup; retry required.')
        archives = []
        for name in (db_name, media_name):
            with ZipFile(stage / name) as archive:
                if archive.testzip() is not None:
                    raise BackupError('Backup ZIP integrity check failed.')
            archives.append({'name': name, **file_hashes(stage / name)})
        run.manifest = {
            'format_version': 1, 'generation': str(run.id),
            'snapshot_at': timezone.now().isoformat(), 'database_vendor': vendor,
            'media_files': len(before), 'archives': archives,
        }
        run.save(update_fields=['manifest'])
        return stage
    except Exception:
        # Preserve a complete prepared generation on delivery failure, but partial
        # snapshot bytes are never eligible for delivery on the next attempt.
        if not run.manifest:
            for path in stage.iterdir():
                if path.is_file() and not path.is_symlink():
                    path.unlink()
        raise


def cleanup_staging(run):
    stage = safe_directory(settings.BACKUP_STAGING_ROOT, run.id)
    if not stage.exists():
        return
    allowed = {'manifest.json'} | {a['name'] for a in run.manifest.get('archives', [])}
    if any(p.is_symlink() or p.name not in allowed or not p.is_file() for p in stage.iterdir()):
        raise BackupError('Unexpected staging contents; cleanup refused.')
    for path in stage.iterdir():
        path.unlink()
    stage.rmdir()


def prune(local, yandex):
    # Completion on both configured destinations is a prerequisite to rotation.
    successful = list(BackupRun.objects.filter(status=BackupRun.Status.SUCCEEDED).order_by('-created_at'))
    for old in successful[2:]:
        if not old.manifest:
            continue  # Already pruned, retain history only.
        local.delete(old)
        if yandex:
            yandex.delete(old)
        cleanup_staging(old)
        old.manifest = {}
        old.cleanup_pending = False
        old.save(update_fields=['manifest', 'cleanup_pending'])


def perform(run, local=None, yandex=None):
    local = local or LocalStorage()
    uses_yandex = getattr(settings, 'BACKUP_YANDEX_ENABLED', True)
    run.status = BackupRun.Status.RUNNING
    run.started_at = run.started_at or timezone.now()
    run.error = ''
    run.save(update_fields=['status', 'started_at', 'error'])
    try:
        yandex = yandex if yandex is not None else (YandexStorage() if uses_yandex else None)
        stage = prepare(run)
        # Reverify both destinations even after a retry/process interruption.
        local.store(run, stage)
        run.local_verified = True
        run.save(update_fields=['local_verified'])
        if yandex:
            yandex.store(run, stage)
            run.yandex_verified = True
            run.save(update_fields=['yandex_verified'])
        run.status = BackupRun.Status.SUCCEEDED
        run.completed_at = timezone.now()
        run.retry_at = None
        run.cleanup_pending = True
        run.save(update_fields=['status', 'completed_at', 'retry_at', 'cleanup_pending'])
        schedule, _ = BackupSchedule.objects.get_or_create(pk=1)
        schedule.last_success_at = run.completed_at
        schedule.next_run_at = run.completed_at + timedelta(seconds=settings.BACKUP_INTERVAL_SECONDS)
        schedule.save(update_fields=['last_success_at', 'next_run_at'])
        try:
            prune(local, yandex)
            cleanup_staging(run)
            run.cleanup_pending = False
            run.save(update_fields=['cleanup_pending'])
        except Exception:
            # Backup success and retention failure must never be conflated.
            run.error = 'Копия сохранена. Очистка старых или временных файлов будет повторена.'
            run.save(update_fields=['error'])
        return run
    except Exception as exc:
        run.status = BackupRun.Status.FAILED
        run.retry_at = timezone.now() + timedelta(seconds=getattr(settings, 'BACKUP_RETRY_SECONDS', 300))
        # Do not log request objects/URLs/tokens/database credentials.
        run.error = str(exc) if isinstance(exc, BackupError) else 'Не удалось создать или отправить копию. Проверьте доступность хранилищ и место на диске.'
        run.save(update_fields=['status', 'retry_at', 'error'])
        logger.warning('Backup %s failed (%s)', run.id, type(exc).__name__)
        return run


def run_due_backup():
    if not getattr(settings, 'BACKUP_ENABLED', False):
        return None
    configured_roots()
    try:
        with backup_lock(blocking=False):
            now = timezone.now()
            # A running status left by a stopped worker is resumed under the lock.
            run = BackupRun.objects.filter(status__in=[BackupRun.Status.PENDING, BackupRun.Status.RUNNING, BackupRun.Status.FAILED]).order_by('created_at').first()
            if run is not None:
                if run.retry_at and run.retry_at > now:
                    return None
                return perform(run)
            schedule, _ = BackupSchedule.objects.get_or_create(pk=1)
            if schedule.last_success_at:
                configured_due = schedule.last_success_at + timedelta(seconds=settings.BACKUP_INTERVAL_SECONDS)
                if schedule.next_run_at != configured_due:
                    schedule.next_run_at = configured_due
                    schedule.save(update_fields=['next_run_at'])
            # Retry cleanup independently instead of waiting for another backup.
            pending = BackupRun.objects.filter(status=BackupRun.Status.SUCCEEDED, cleanup_pending=True)
            if pending.exists():
                try:
                    local = LocalStorage()
                    yandex = YandexStorage() if getattr(settings, 'BACKUP_YANDEX_ENABLED', True) else None
                    prune(local, yandex)
                    for previous in pending:
                        cleanup_staging(previous)
                        previous.cleanup_pending = False
                        previous.error = ''
                        previous.save(update_fields=['cleanup_pending', 'error'])
                except Exception:
                    logger.warning('Backup cleanup will be retried.')
            if schedule.next_run_at and schedule.next_run_at > now:
                return None
            return perform(BackupRun.objects.create())
    except BlockingIOError:
        return None
