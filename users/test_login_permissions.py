from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from users.role_utils import DIRECTOR_EMAIL
from users.views import DIRECTOR_PASSWORD

User = get_user_model()


class LoginAndPermissionsTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")
        self.employee = User.objects.create_user(
            email="employee@test.com",
            password="emp-pass",
            full_name="Employee",
            phone_number="1111111111",
            post_user="employee",
            is_active=True,
        )

    def test_director_login_creates_session(self):
        response = self.client.post(
            reverse("login"),
            {"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], "/director/")
        director = User.objects.get(email=DIRECTOR_EMAIL)
        self.assertTrue(director.is_active)
        self.assertTrue(director.is_staff)

    def test_active_employee_login_redirects_to_profile(self):
        response = self.client.post(
            reverse("login"),
            {"email": "employee@test.com", "password": "emp-pass"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], "/profile/")

    def test_unapproved_user_cannot_login(self):
        User.objects.create_user(
            email="pending@test.com",
            password="pending-pass",
            full_name="Pending",
            phone_number="2222222222",
            post_user="unapproved",
            is_active=True,
        )
        response = self.client.post(
            reverse("login"),
            {"email": "pending@test.com", "password": "pending-pass"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_director_can_open_employee_profile(self):
        self.client.post(
            reverse("login"),
            {"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD},
        )
        response = self.client.get(
            reverse("profile_employee", args=[self.employee.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сбросить пароль")

    def test_regular_user_cannot_open_director_employee_profile(self):
        self.client.post(
            reverse("login"),
            {"email": "employee@test.com", "password": "emp-pass"},
        )
        response = self.client.get(
            reverse("profile_employee", args=[self.employee.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], "/")
        self.assertNotContains(response, "Сбросить пароль")

    def test_director_can_reset_employee_password(self):
        self.client.post(
            reverse("login"),
            {"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD},
        )
        response = self.client.post(
            reverse("profile_employee", args=[self.employee.id]),
            {"action": "reset_password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temp-password-value")
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.check_password("emp-pass"))
