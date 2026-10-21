from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from users.role_utils import DIRECTOR_EMAIL
from backups.models import BackupConnection, BackupRun
from backups.tokens import decrypt_token


@override_settings(
    YANDEX_CLIENT_ID='test-client', YANDEX_CLIENT_SECRET='test-secret',
    YANDEX_REDIRECT_URI='http://localhost/director/backups/yandex/callback/',
    YANDEX_ACCESS_TOKEN='', BACKUP_ENCRYPTION_KEY=Fernet.generate_key().decode(),
)
class BackupConnectionViewsTests(TestCase):
    def setUp(self):
        self.director = get_user_model().objects.create_user(
            email=DIRECTOR_EMAIL, password='test-password', full_name='Director',
            is_active=True, is_staff=True, post_user='senior_manager',
        )
        self.client.force_login(self.director)

    def test_existing_director_login_role_does_not_need_new_role(self):
        self.assertTrue(self.director.has_perm('backups.manage_backups'))
        response = self.client.get(reverse('home_director'))
        self.assertContains(response, 'Подключить Яндекс Диск')
        self.assertNotContains(response, 'Создать копию сейчас')

    def test_manager_cannot_read_backup_status_even_with_permission(self):
        manager = get_user_model().objects.create_user(
            email='backup-manager@example.com', password='test',
            is_active=True, post_user='manager',
        )
        manager.user_permissions.add(Permission.objects.get(codename='manage_backups'))
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('backups:status')).status_code, 403)

    def test_explicit_permission_is_required_and_not_regranted_by_activity(self):
        self.director.user_permissions.clear()
        self.assertEqual(self.client.get(reverse('backups:yandex_connect')).status_code, 403)
        self.assertFalse(self.director.user_permissions.filter(codename='manage_backups').exists())

    def test_oauth_uses_state_and_pkce(self):
        response = self.client.get(reverse('backups:yandex_connect'))
        query = parse_qs(urlsplit(response['Location']).query)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['response_type'], ['code'])
        self.assertEqual(query['state'][0], self.client.session['yandex_backup_oauth']['state'])

    @patch('backups.views.requests.post')
    def test_wrong_state_never_exchanges_code(self, post):
        self.client.get(reverse('backups:yandex_connect'))
        self.client.get(reverse('backups:yandex_callback'), {'code':'secret-code', 'state':'wrong'})
        post.assert_not_called()
        self.assertFalse(BackupConnection.objects.exists())

    @patch('backups.views.requests.post')
    def test_success_saves_encrypted_tokens_and_callback_cannot_replay(self, post):
        response = Mock()
        response.json.return_value = {'access_token':'access-secret', 'refresh_token':'refresh-secret', 'expires_in':3600}
        post.return_value = response
        self.client.get(reverse('backups:yandex_connect'))
        state = self.client.session['yandex_backup_oauth']['state']
        url = reverse('backups:yandex_callback')
        self.client.get(url, {'code':'secret-code', 'state':state})
        connection = BackupConnection.objects.get(pk=1)
        self.assertNotIn('access-secret', connection.access_token_encrypted)
        self.assertEqual(decrypt_token(connection.access_token_encrypted), 'access-secret')
        self.client.get(url, {'code':'secret-code', 'state':state})
        self.assertEqual(post.call_count, 1)
        self.assertFalse(BackupRun.objects.exists())
