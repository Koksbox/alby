import datetime as dt

from django.contrib.auth import authenticate, get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from users.role_utils import (
    DIRECTOR_EMAIL,
    can_manage_staff,
    get_shift_period,
    is_director,
    is_manager,
    reset_user_password,
)

User = get_user_model()


class RoleUtilsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_is_director_by_email(self):
        director = User.objects.create_user(
            email=DIRECTOR_EMAIL,
            password="pass",
            full_name="Director",
            is_active=True,
        )
        employee = User.objects.create_user(
            email="emp@test.com",
            password="pass",
            full_name="Emp",
            post_user="employee",
            is_active=True,
        )
        self.assertTrue(is_director(director))
        self.assertFalse(is_director(employee))

    def test_is_manager_and_can_manage_staff(self):
        junior = User.objects.create_user(
            email="junior@test.com",
            password="pass",
            full_name="Junior",
            post_user="junior_manager",
            is_active=True,
        )
        manager = User.objects.create_user(
            email="manager@test.com",
            password="pass",
            full_name="Manager",
            post_user="manager",
            is_active=True,
        )
        self.assertTrue(is_manager(junior))
        self.assertTrue(is_manager(manager))
        self.assertFalse(can_manage_staff(junior))
        self.assertTrue(can_manage_staff(manager))

    def test_get_shift_period_date_range(self):
        request = self.factory.get(
            "/",
            {"date_from": "2025-01-10", "date_to": "2025-01-20"},
        )
        start_dt, end_dt, filter_mode, date_from, date_to, selected_month = get_shift_period(
            request
        )
        self.assertEqual(filter_mode, "range")
        self.assertEqual(date_from, "2025-01-10")
        self.assertEqual(date_to, "2025-01-20")
        self.assertIsNone(selected_month)
        self.assertEqual(
            start_dt,
            timezone.make_aware(dt.datetime(2025, 1, 10, 0, 0, 0)),
        )
        self.assertEqual(
            end_dt,
            timezone.make_aware(dt.datetime(2025, 1, 21, 0, 0, 0)),
        )

    def test_get_shift_period_month_fallback(self):
        request = self.factory.get("/", {"month": "2025-03"})
        start_dt, end_dt, filter_mode, date_from, date_to, selected_month = get_shift_period(
            request
        )
        self.assertEqual(filter_mode, "month")
        self.assertEqual(date_from, "")
        self.assertEqual(date_to, "")
        self.assertEqual(start_dt.month, 3)
        self.assertEqual(start_dt.day, 1)
        self.assertEqual(end_dt.month, 4)
        self.assertEqual(end_dt.day, 1)

    def test_reset_user_password_changes_credentials(self):
        user = User.objects.create_user(
            email="reset@test.com",
            password="old-pass",
            full_name="Reset Me",
            post_user="employee",
            is_active=True,
        )
        temp_password = reset_user_password(user)
        self.assertEqual(len(temp_password), 12)
        user.refresh_from_db()
        self.assertFalse(user.check_password("old-pass"))
        self.assertTrue(user.check_password(temp_password))
        self.assertIsNotNone(
            authenticate(username="reset@test.com", password=temp_password)
        )
