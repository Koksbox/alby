from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from backups.engine import run_due_backup
from backups.locking import backup_lock
from backups.models import BackupConnection, BackupRun, BackupSchedule
from backups.providers import BackupError, YandexStorage
from backups.tokens import decrypt_token, save_connection_tokens
from backups.views import connection_status
from users.role_utils import DIRECTOR_EMAIL


class DisconnectYandexDiskTests(TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = self.root / '.env'
        self.env.write_text('YANDEX_CLIENT_SECRET=kept-secret\nYANDEX_ACCESS_TOKEN=kept-token\nBACKUP_ENABLED=1\n')
        self.overrides = override_settings(
            BASE_DIR=self.root, BACKUP_STAGING_ROOT=self.root / 'staging',
            BACKUP_LOCAL_ROOT=self.root / 'local', STATIC_ROOT=self.root / 'static',
            MEDIA_ROOT=self.root / 'media', BACKUP_ENABLED=True, BACKUP_YANDEX_ENABLED=True,
            YANDEX_ACCESS_TOKEN='fallback-token', YANDEX_REFRESH_TOKEN='fallback-refresh',
            YANDEX_CLIENT_ID='client', YANDEX_CLIENT_SECRET='secret',
            YANDEX_REDIRECT_URI='http://localhost/director/backups/yandex/callback/',
            BACKUP_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        )
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        self.connection = save_connection_tokens({'access_token': 'old-token', 'refresh_token': 'old-refresh'})

    def disconnect(self):
        output = StringIO()
        call_command('disconnect_yandex_disk', stdout=output)
        return output.getvalue()

    def test_detach_preserves_tokens_environment_password_history_and_archives(self):
        user = get_user_model().objects.create_user(email=DIRECTOR_EMAIL, password='unchanged-password')
        run = BackupRun.objects.create(status='succeeded', manifest={'generation': 'kept'})
        schedule = BackupSchedule.objects.create(pk=1)
        archive = self.root / 'alby_db_kept.zip'
        archive.write_bytes(b'keep archive')
        before_env = self.env.read_bytes()
        before_tokens = (self.connection.access_token_encrypted, self.connection.refresh_token_encrypted)
        session = SessionStore()
        session['_auth_user_id'] = str(user.pk)
        session['yandex_backup_oauth'] = {'state': 'pending-state'}
        session.save()
        self.disconnect()
        self.connection.refresh_from_db()
        self.assertIsNotNone(self.connection.disconnected_at)
        self.assertFalse(self.connection.is_connected)
        self.assertEqual((self.connection.access_token_encrypted, self.connection.refresh_token_encrypted), before_tokens)
        self.assertEqual(self.env.read_bytes(), before_env)
        user.refresh_from_db()
        self.assertTrue(user.check_password('unchanged-password'))
        self.assertEqual(Session.objects.get(pk=session.session_key).get_decoded(), {'_auth_user_id': str(user.pk)})
        run.refresh_from_db()
        self.assertEqual(run.manifest, {'generation': 'kept'})
        self.assertTrue(BackupSchedule.objects.filter(pk=schedule.pk).exists())
        self.assertEqual(archive.read_bytes(), b'keep archive')

    def test_environment_fallback_cannot_reattach_and_status_is_disconnected(self):
        self.disconnect()
        self.assertFalse(connection_status()['connected'])
        with patch('backups.providers.save_connection_tokens') as save:
            with self.assertRaisesRegex(BackupError, 'detached'):
                YandexStorage()
            save.assert_not_called()

    def test_worker_waits_without_resuming_old_jobs_or_creating_new_backups(self):
        self.disconnect()
        run = BackupRun.objects.create(status='failed', error='previous error')
        with patch('backups.engine.perform') as perform, patch('backups.engine.prune') as prune:
            self.assertIsNone(run_due_backup())
            perform.assert_not_called()
            prune.assert_not_called()
        self.assertEqual(BackupRun.objects.count(), 1)
        run.refresh_from_db()
        self.assertEqual(run.error, 'previous error')

    def test_detach_before_first_connection_also_blocks_environment_import(self):
        BackupConnection.objects.all().delete()
        self.disconnect()
        self.assertIsNotNone(BackupConnection.objects.get(pk=1).disconnected_at)
        self.assertFalse(connection_status()['connected'])
        with self.assertRaisesRegex(BackupError, 'detached'):
            YandexStorage()

    def test_busy_worker_leaves_connection_intact(self):
        with backup_lock(blocking=False):
            with self.assertRaisesRegex(CommandError, 'backup is running'):
                self.disconnect()
        self.connection.refresh_from_db()
        self.assertIsNone(self.connection.disconnected_at)
        self.assertTrue(self.connection.is_connected)

    def test_detach_is_idempotent_and_does_not_require_environment_file(self):
        self.env.unlink()
        self.disconnect()
        self.connection.refresh_from_db()
        detached_at = self.connection.disconnected_at
        self.disconnect()
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.disconnected_at, detached_at)
        self.assertEqual(decrypt_token(self.connection.access_token_encrypted), 'old-token')

    @patch('backups.views.requests.post')
    def test_new_oauth_connection_reenables_worker_without_using_old_env_token(self, post):
        director = get_user_model().objects.create_user(
            email=DIRECTOR_EMAIL, password='password', full_name='Director',
            is_active=True, is_staff=True, post_user='senior_manager',
        )
        self.client.force_login(director)
        self.client.get(reverse('backups:yandex_connect'))
        old_state = self.client.session['yandex_backup_oauth']['state']
        self.disconnect()
        self.client.get(reverse('backups:yandex_callback'), {'state': old_state, 'code': 'old-code'})
        post.assert_not_called()
        self.client.get(reverse('backups:yandex_connect'))
        state = self.client.session['yandex_backup_oauth']['state']
        post.return_value.json.return_value = {'access_token': 'new-token', 'refresh_token': 'new-refresh', 'expires_in': 3600}
        self.client.get(reverse('backups:yandex_callback'), {'state': state, 'code': 'new-code'})
        self.connection.refresh_from_db()
        self.assertIsNone(self.connection.disconnected_at)
        self.assertTrue(self.connection.is_connected)
        self.assertEqual(decrypt_token(self.connection.access_token_encrypted), 'new-token')
        self.assertEqual(decrypt_token(self.connection.refresh_token_encrypted), 'new-refresh')
        self.assertTrue(connection_status()['connected'])
        self.assertEqual(YandexStorage().connection.pk, self.connection.pk)
        with patch('backups.engine.perform') as perform:
            run_due_backup()
            perform.assert_called_once()
