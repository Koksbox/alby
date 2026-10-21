from datetime import timedelta
from pathlib import Path
import shutil
from types import SimpleNamespace
import sqlite3
import tempfile
from unittest.mock import Mock, patch
from zipfile import ZipFile

from cryptography.fernet import Fernet
from django.test import TransactionTestCase, SimpleTestCase, override_settings
from django.utils import timezone

from backups.engine import configured_roots, perform, prepare, run_due_backup
from backups.models import BackupConnection, BackupRun, BackupSchedule
from backups.providers import BackupError, LocalStorage, YandexStorage, file_hashes
from backups.tokens import decrypt_token, save_connection_tokens


class BackupEngineTests(TransactionTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.media = root / 'media'
        self.media.mkdir()
        (self.media / 'photos').mkdir()
        (self.media / 'photos' / 'task.jpg').write_bytes(b'original image content')
        self.staging, self.local = root / 'staging', root / 'local'
        self.overrides = override_settings(
            BACKUP_ENABLED=True, BACKUP_YANDEX_ENABLED=True,
            BACKUP_INTERVAL_SECONDS=7200, BACKUP_RETRY_SECONDS=30,
            BACKUP_STAGING_ROOT=self.staging, BACKUP_LOCAL_ROOT=self.local,
            MEDIA_ROOT=self.media, BACKUP_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        )
        self.overrides.enable()
        self.yandex = Mock()

    def tearDown(self):
        self.overrides.disable()
        self.temporary.cleanup()

    def test_snapshot_contains_restorable_sqlite_and_relative_media(self):
        run = BackupRun.objects.create()
        stage = prepare(run)
        self.assertEqual(len(run.manifest['archives']), 2)
        for entry in run.manifest['archives']:
            self.assertEqual(file_hashes(stage / entry['name'])['sha256'], entry['sha256'])
            with ZipFile(stage / entry['name']) as archive:
                self.assertIsNone(archive.testzip())
                if 'media' in entry['name']:
                    self.assertEqual(archive.read('media/photos/task.jpg'), b'original image content')
                else:
                    restored = Path(self.temporary.name) / 'restored.sqlite3'
                    restored.write_bytes(archive.read('database.sqlite3'))
                    with sqlite3.connect(restored) as db:
                        self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
                        self.assertEqual(db.execute('SELECT count(*) FROM backups_backuprun').fetchone()[0], 1)

    def test_third_complete_generation_keeps_two_newest_on_both_targets(self):
        runs = []
        for _ in range(3):
            run = perform(BackupRun.objects.create(), yandex=self.yandex)
            self.assertEqual(run.status, BackupRun.Status.SUCCEEDED)
            runs.append(run)
        self.assertFalse((self.local / str(runs[0].id)).exists())
        self.assertTrue((self.local / str(runs[1].id) / 'manifest.json').exists())
        self.assertTrue((self.local / str(runs[2].id) / 'manifest.json').exists())
        self.yandex.delete.assert_called_once()
        self.assertEqual(self.yandex.delete.call_args[0][0].id, runs[0].id)
        self.assertFalse((self.staging / str(runs[2].id)).exists())
        self.assertTrue((self.media / 'photos/task.jpg').exists())

    def test_failed_second_destination_preserves_previous_and_reuses_generation(self):
        first = perform(BackupRun.objects.create(), yandex=self.yandex)
        second = perform(BackupRun.objects.create(), yandex=self.yandex)
        third = BackupRun.objects.create()
        self.yandex.store.side_effect = BackupError('Upload unavailable.')
        failed = perform(third, yandex=self.yandex)
        self.assertEqual(failed.status, BackupRun.Status.FAILED)
        self.assertTrue((self.local / str(first.id)).exists())
        self.assertTrue((self.local / str(second.id)).exists())
        self.assertTrue((self.staging / str(third.id)).exists())
        self.yandex.delete.assert_not_called()
        manifest = failed.manifest.copy()
        self.yandex.store.side_effect = None
        retried = perform(failed, yandex=self.yandex)
        self.assertEqual(retried.status, BackupRun.Status.SUCCEEDED)
        self.assertEqual(manifest, retried.manifest)
        self.assertEqual(BackupRun.objects.count(), 3)

    def test_cleanup_failure_keeps_success_and_is_retried(self):
        local = LocalStorage()
        with patch('backups.engine.cleanup_staging', side_effect=BackupError('busy')):
            run = perform(BackupRun.objects.create(), local=local, yandex=self.yandex)
        self.assertEqual(run.status, BackupRun.Status.SUCCEEDED)
        self.assertTrue(run.cleanup_pending)
        with patch('backups.engine.YandexStorage', return_value=self.yandex):
            self.assertIsNone(run_due_backup())
        run.refresh_from_db()
        self.assertFalse(run.cleanup_pending)
        self.assertFalse((self.staging / str(run.id)).exists())

    def test_worker_does_not_run_before_due_and_disabled_does_nothing(self):
        BackupSchedule.objects.create(pk=1, next_run_at=timezone.now() + timedelta(hours=1))
        self.assertIsNone(run_due_backup())
        self.assertEqual(BackupRun.objects.count(), 0)
        with override_settings(BACKUP_ENABLED=False):
            self.assertIsNone(run_due_backup())

    def test_worker_records_missing_yandex_as_retryable_failure(self):
        with override_settings(YANDEX_ACCESS_TOKEN=''):
            run = run_due_backup()
        self.assertEqual(run.status, BackupRun.Status.FAILED)
        self.assertIsNotNone(run.retry_at)
        self.assertIn('not connected', run.error)
        self.assertIsNone(run_due_backup())
        self.assertEqual(BackupRun.objects.count(), 1)

    def test_symlink_and_changed_media_are_not_published(self):
        (self.media / 'link.jpg').symlink_to(self.media / 'photos/task.jpg')
        run = perform(BackupRun.objects.create(), yandex=self.yandex)
        self.assertEqual(run.status, BackupRun.Status.FAILED)
        self.yandex.store.assert_not_called()
        self.assertFalse((self.local / str(run.id)).exists())

    def test_local_deletion_refuses_foreign_files_and_symlink(self):
        run = perform(BackupRun.objects.create(), yandex=self.yandex)
        target = self.local / str(run.id)
        (target / 'foreign.txt').write_text('do not delete')
        with self.assertRaises(BackupError):
            LocalStorage().delete(run)
        self.assertTrue((target / 'foreign.txt').exists())
        (target / 'foreign.txt').unlink()
        (target / 'manifest.json').unlink()
        (target / 'manifest.json').symlink_to(self.media / 'photos/task.jpg')
        with self.assertRaises(BackupError):
            LocalStorage().delete(run)
        self.assertTrue((self.media / 'photos/task.jpg').exists())

    def test_token_encryption_and_environment_connection(self):
        connection = save_connection_tokens({'access_token': 'secret', 'refresh_token': 'refresh', 'expires_in': 3600})
        self.assertNotIn('secret', connection.access_token_encrypted)
        self.assertEqual(decrypt_token(connection.access_token_encrypted), 'secret')
        self.assertGreater(connection.expires_at, timezone.now())
        BackupConnection.objects.all().delete()
        with override_settings(YANDEX_ACCESS_TOKEN='env-token', YANDEX_REFRESH_TOKEN='env-refresh'):
            provider = YandexStorage()
        self.assertEqual(decrypt_token(provider.connection.access_token_encrypted), 'env-token')

    def test_target_cannot_be_inside_media(self):
        with override_settings(BACKUP_LOCAL_ROOT=self.media / 'backups'):
            with self.assertRaises(BackupError):
                configured_roots()

    def test_local_cleanup_interruption_keeps_marker_until_archives_are_removed(self):
        run = perform(BackupRun.objects.create(), yandex=self.yandex)
        target = self.local / str(run.id)
        original_unlink = Path.unlink
        calls = []
        def interrupted(path, *args, **kwargs):
            calls.append(path.name)
            if len(calls) == 2:
                raise OSError('interrupted')
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', interrupted):
            with self.assertRaises(OSError):
                LocalStorage().delete(run)
        self.assertTrue((target / 'manifest.json').exists())
        self.assertNotIn('manifest.json', calls)
        LocalStorage().delete(run)
        self.assertFalse(target.exists())

    def test_local_cleanup_resumes_after_marker_removed_before_rmdir(self):
        run = perform(BackupRun.objects.create(), yandex=self.yandex)
        target = self.local / str(run.id)
        for path in target.iterdir():
            path.unlink()
        LocalStorage().delete(run)
        self.assertFalse(target.exists())

    def test_rotation_cleans_old_staging_before_discarding_manifest(self):
        with patch('backups.engine.cleanup_staging', side_effect=BackupError('busy')):
            first = perform(BackupRun.objects.create(), yandex=self.yandex)
        self.assertTrue((self.staging / str(first.id)).exists())
        perform(BackupRun.objects.create(), yandex=self.yandex)
        perform(BackupRun.objects.create(), yandex=self.yandex)
        self.assertFalse((self.staging / str(first.id)).exists())
        first.refresh_from_db()
        self.assertEqual(first.manifest, {})

    def test_changed_interval_recomputes_due_time_from_last_success(self):
        last_success = timezone.now() - timedelta(hours=2)
        BackupSchedule.objects.create(pk=1, last_success_at=last_success,
                                      next_run_at=last_success + timedelta(days=3))
        with override_settings(BACKUP_INTERVAL_SECONDS=3600), patch('backups.engine.perform') as mocked:
            run_due_backup()
        mocked.assert_called_once()
        schedule = BackupSchedule.objects.get(pk=1)
        self.assertEqual(schedule.next_run_at, last_success + timedelta(hours=1))

    def test_lost_stage_recovers_exact_snapshot_from_verified_local_copy(self):
        self.yandex.store.side_effect = BackupError('Network unavailable.')
        run = perform(BackupRun.objects.create(), yandex=self.yandex)
        manifest = run.manifest.copy()
        stage = self.staging / str(run.id)
        shutil.rmtree(stage)
        # Working data can change after the snapshot. Recovery must not read it.
        (self.media / 'photos/task.jpg').write_bytes(b'new working photograph')
        self.yandex.store.side_effect = None
        with patch('backups.engine._sqlite_snapshot', side_effect=AssertionError('must not resnapshot')):
            retried = perform(run, yandex=self.yandex)
        self.assertEqual(retried.status, BackupRun.Status.SUCCEEDED)
        self.assertEqual(retried.manifest, manifest)
        self.assertEqual((self.media / 'photos/task.jpg').read_bytes(), b'new working photograph')
        local = self.local / str(run.id)
        for entry in manifest['archives']:
            self.assertEqual(file_hashes(local / entry['name']), {k: entry[k] for k in ('sha256', 'md5', 'size')})
            if 'media' in entry['name']:
                with ZipFile(local / entry['name']) as archive:
                    self.assertEqual(archive.read('media/photos/task.jpg'), b'original image content')

    def test_corrupt_stage_recovers_from_local_and_rejects_corrupt_local_source(self):
        self.yandex.store.side_effect = BackupError('Network unavailable.')
        run = perform(BackupRun.objects.create(), yandex=self.yandex)
        stage = self.staging / str(run.id)
        name = run.manifest['archives'][0]['name']
        (stage / name).write_bytes(b'corrupt temporary archive')
        self.assertEqual(prepare(run), stage.resolve())
        expected = run.manifest['archives'][0]['sha256']
        self.assertEqual(file_hashes(stage / name)['sha256'], expected)
        (stage / name).unlink()
        (self.local / str(run.id) / name).write_bytes(b'corrupt recovery archive')
        with patch('backups.engine._sqlite_snapshot') as snapshot:
            with self.assertRaises(BackupError):
                prepare(run)
        snapshot.assert_not_called()

    def test_yandex_401_refreshes_encrypted_tokens_and_retries_with_new_token(self):
        save_connection_tokens({'access_token': 'old-token', 'refresh_token': 'old-refresh'})
        provider = YandexStorage()
        unauthorized, success = Mock(status_code=401), Mock(status_code=200)
        refreshed = Mock(status_code=200)
        refreshed.json.return_value = {'access_token': 'new-token', 'refresh_token': 'new-refresh', 'expires_in': 3600}
        provider.session = Mock()
        provider.session.request.side_effect = [unauthorized, success]
        provider.session.post.return_value = refreshed
        result = provider._request('GET', '/resources', params={'path': 'app:/test'})
        self.assertIs(result, success)
        self.assertEqual(provider.session.request.call_args_list[0].kwargs['headers']['Authorization'], 'OAuth old-token')
        self.assertEqual(provider.session.request.call_args_list[1].kwargs['headers']['Authorization'], 'OAuth new-token')
        connection = BackupConnection.objects.get(pk=1)
        self.assertNotIn('new-token', connection.access_token_encrypted)
        self.assertEqual(decrypt_token(connection.access_token_encrypted), 'new-token')
        self.assertEqual(decrypt_token(connection.refresh_token_encrypted), 'new-refresh')

    def test_yandex_transport_publishes_archives_then_marker_and_waits_for_delete(self):
        import hashlib
        import json
        save_connection_tokens({'access_token': 'token'})
        provider = YandexStorage()
        objects, directories, links, events = {}, set(), {}, []
        deleting = {}
        def response(status, payload=None):
            result = Mock(status_code=status)
            result.json.return_value = payload
            return result
        def request(method, url, **kwargs):
            endpoint = url.removeprefix(provider.API)
            path = kwargs['params']['path']
            events.append((method, endpoint, path))
            if method == 'PUT' and endpoint == '/resources':
                directories.add(path)
                return response(201)
            if method == 'GET' and endpoint == '/resources/upload':
                href = 'https://uploader.disk.yandex.net/' + str(len(links))
                links[href] = path
                return response(200, {'href': href})
            if method == 'GET' and endpoint == '/resources/download':
                href = 'https://downloader.disk.yandex.ru/' + str(len(links))
                links[href] = path
                return response(200, {'href': href})
            if method == 'DELETE' and endpoint == '/resources':
                self.assertEqual(kwargs['params']['permanently'], 'true')
                deleting[path] = 2
                return response(202)
            if method == 'GET' and endpoint == '/resources':
                if path in deleting:
                    deleting[path] -= 1
                    if deleting[path] == 0:
                        for key in list(objects):
                            if key.startswith(path + '/'):
                                del objects[key]
                        directories.discard(path)
                        del deleting[path]
                if path in objects:
                    data = objects[path]
                    return response(200, {'type': 'file', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
                if path in directories:
                    items = [{'name': key.rsplit('/', 1)[-1], 'type': 'file'} for key in objects if key.rsplit('/', 1)[0] == path]
                    return response(200, {'type': 'dir', '_embedded': {'total': len(items), 'items': items}})
                return response(404)
            raise AssertionError((method, endpoint, path))
        def put(href, data, **kwargs):
            path = links[href]
            events.append(('UPLOAD', path))
            objects[path] = data.read()
            return response(201)
        def get(href, **kwargs):
            return response(200, json.loads(objects[links[href]]))
        provider.session = Mock()
        provider.session.request.side_effect = request
        provider.session.put.side_effect = put
        provider.session.get.side_effect = get
        run = BackupRun.objects.create()
        stage = prepare(run)
        with patch('backups.providers.time.sleep'):
            provider.store(run, stage)
            uploaded = [event[1] for event in events if event[0] == 'UPLOAD']
            self.assertEqual(len(uploaded), 3)
            self.assertTrue(uploaded[-1].endswith('/manifest.json'))
            provider.delete(run)
        self.assertFalse(objects)
        self.assertEqual(sum(event[0] == 'DELETE' for event in events), 1)

    def test_local_completed_generation_cannot_be_replaced_by_different_snapshot(self):
        from copy import deepcopy
        run = perform(BackupRun.objects.create(), yandex=self.yandex)
        target = self.local / str(run.id)
        originals = {path.name: path.read_bytes() for path in target.iterdir()}
        replacement = Path(self.temporary.name) / 'replacement'
        replacement.mkdir()
        run.manifest = deepcopy(run.manifest)
        run.manifest['snapshot_at'] = 'different snapshot after database restore'
        for entry in run.manifest['archives']:
            path = replacement / entry['name']
            path.write_bytes(b'new source snapshot must not overwrite original')
            entry.update(file_hashes(path))
        with self.assertRaisesRegex(BackupError, 'published local backup'):
            LocalStorage().store(run, replacement)
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, originals)

    def test_yandex_completed_generation_collision_stops_before_archive_upload(self):
        save_connection_tokens({'access_token': 'token'})
        provider = YandexStorage()
        provider.session = Mock()
        remote_marker = Mock(status_code=200)
        remote_marker.json.return_value = {'type': 'file', 'size': 0, 'sha256': 'different-published-manifest'}
        provider.session.request.return_value = remote_marker
        run = BackupRun.objects.create()
        stage = prepare(run)
        with self.assertRaisesRegex(BackupError, 'published Yandex backup'):
            provider.store(run, stage)
        provider.session.put.assert_not_called()
        self.assertEqual(provider.session.request.call_count, 1)
        request = provider.session.request.call_args
        self.assertEqual(request.args, ('GET', provider.API + '/resources'))
        self.assertTrue(request.kwargs['params']['path'].endswith('/manifest.json'))


class ProviderVerificationTests(SimpleTestCase):
    def test_yandex_checksum_and_size_must_match(self):
        entry = {'size': 10, 'sha256': 'abc', 'md5': 'def'}
        self.assertTrue(YandexStorage._matches({'type': 'file', 'size': 10, 'sha256': 'abc'}, entry))
        self.assertFalse(YandexStorage._matches({'type': 'file', 'size': 10, 'sha256': 'wrong', 'md5': 'def'}, entry))
        self.assertFalse(YandexStorage._matches({'type': 'file', 'size': 10}, entry))
        self.assertFalse(YandexStorage._matches({'type': 'file', 'size': 11, 'sha256': 'abc'}, entry))
        self.assertTrue(YandexStorage._matches({'type': 'file', 'size': 10, 'md5': 'def'}, entry))

    def test_yandex_upload_is_not_successful_until_remote_hash_matches(self):
        provider = YandexStorage.__new__(YandexStorage)
        provider.session = Mock()
        provider._metadata = Mock(return_value={'type': 'file', 'size': 3, 'sha256': 'wrong'})
        response = Mock()
        response.json.return_value = {'href': 'https://uploader.disk.yandex.net/upload'}
        provider._request = Mock(return_value=response)
        provider.session.put.return_value.status_code = 201
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive.zip'
            path.write_bytes(b'zip')
            with patch('backups.providers.time.sleep'):
                with self.assertRaises(BackupError):
                    provider._upload(path, 'app:/backup/archive.zip', file_hashes(path))
        self.assertGreater(provider._metadata.call_count, 1)

    def test_yandex_rejects_external_upload_address(self):
        provider = YandexStorage.__new__(YandexStorage)
        provider.session = Mock()
        provider._metadata = Mock(return_value=None)
        response = Mock()
        response.json.return_value = {'href': 'https://attacker.example/upload'}
        provider._request = Mock(return_value=response)
        with self.assertRaises(BackupError):
            provider._upload(Path('/unused'), 'app:/backup/archive.zip', {'size': 3, 'sha256': 'a', 'md5': 'b'})
        provider.session.put.assert_not_called()


    def test_yandex_accepted_delete_is_not_success_until_resource_disappears(self):
        import uuid
        provider = YandexStorage.__new__(YandexStorage)
        provider.root = 'app:/AlbyBackups'
        run = SimpleNamespace(id=uuid.uuid4(), manifest={'archives': [{'name': 'alby_db_test.zip'}, {'name': 'alby_media_test.zip'}]})
        names = ['alby_db_test.zip', 'alby_media_test.zip', 'manifest.json']
        provider._metadata = Mock(return_value={'type': 'dir', '_embedded': {'total': 3, 'items': [{'name': name, 'type': 'file'} for name in names]}})
        download_link = Mock(status_code=200)
        download_link.json.return_value = {'href': 'https://downloader.disk.yandex.ru/manifest'}
        accepted = Mock(status_code=202)
        provider._request = Mock(side_effect=[download_link, accepted])
        provider.session = Mock()
        provider.session.get.return_value.status_code = 200
        provider.session.get.return_value.json.return_value = run.manifest
        with patch('backups.providers.time.sleep'):
            with self.assertRaisesRegex(BackupError, 'still pending'):
                provider.delete(run)
        self.assertEqual(provider._request.call_args_list[1].args[:2], ('DELETE', '/resources'))
