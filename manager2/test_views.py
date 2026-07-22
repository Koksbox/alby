import datetime as dt

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import TimeEntry

User = get_user_model()


class ManagerCabinetViewsTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")
        self.manager = User.objects.create_user(
            email="cabinet-manager@test.com",
            password="mgr-pass",
            full_name="Cabinet Manager",
            phone_number="4444444444",
            post_user="manager",
            is_active=True,
        )
        self.junior_manager = User.objects.create_user(
            email="junior-cabinet@test.com",
            password="jr-pass",
            full_name="Junior Cabinet",
            phone_number="5555555555",
            post_user="junior_manager",
            is_active=True,
        )
        self.employee = User.objects.create_user(
            email="cabinet-employee@test.com",
            password="emp-pass",
            full_name="Cabinet Employee",
            phone_number="6666666666",
            post_user="employee",
            is_active=True,
        )

    def _login(self, email, password):
        self.client.post(reverse("login"), {"email": email, "password": password})

    def _create_shift(self, user, start, end):
        return TimeEntry.objects.create(
            user=user,
            timer_type="shift",
            start_time=start,
            end_time=end,
        )

    def test_manager_can_reset_employee_password(self):
        self._login("cabinet-manager@test.com", "mgr-pass")
        response = self.client.post(
            reverse("profile_employee_manager", args=[self.employee.id]),
            {"action": "reset_password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temp-password-value")
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.check_password("emp-pass"))

    def test_junior_manager_cannot_reset_employee_password(self):
        self._login("junior-cabinet@test.com", "jr-pass")
        response = self.client.get(
            reverse("profile_employee_manager", args=[self.employee.id]),
            follow=True,
        )
        self.assertContains(response, "Недостаточно прав")

    def test_employee_shifts_filters_by_date_range(self):
        self._login("cabinet-manager@test.com", "mgr-pass")

        jan_start = timezone.make_aware(dt.datetime(2025, 1, 5, 8, 0, 0))
        jan_end = timezone.make_aware(dt.datetime(2025, 1, 5, 12, 0, 0))
        feb_start = timezone.make_aware(dt.datetime(2025, 2, 5, 8, 0, 0))
        feb_end = timezone.make_aware(dt.datetime(2025, 2, 5, 12, 0, 0))

        self._create_shift(self.employee, jan_start, jan_end)
        self._create_shift(self.employee, feb_start, feb_end)

        response = self.client.get(
            reverse("employee_shifts", args=[self.employee.id]),
            {"date_from": "2025-01-01", "date_to": "2025-01-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filter_mode"], "range")
        self.assertEqual(len(response.context["time_entries"]), 1)
        self.assertAlmostEqual(response.context["total_salary"], 560.0, places=2)

    def test_manager_history_filters_by_date_range(self):
        self._login("cabinet-manager@test.com", "mgr-pass")

        from manager2.models import TimeManger

        jan_start = timezone.make_aware(dt.datetime(2025, 1, 8, 10, 0, 0))
        jan_end = timezone.make_aware(dt.datetime(2025, 1, 8, 14, 0, 0))
        feb_start = timezone.make_aware(dt.datetime(2025, 2, 8, 10, 0, 0))
        feb_end = timezone.make_aware(dt.datetime(2025, 2, 8, 14, 0, 0))

        TimeManger.objects.create(
            manager=self.manager, start_time=jan_start, end_time=jan_end
        )
        TimeManger.objects.create(
            manager=self.manager, start_time=feb_start, end_time=feb_end
        )

        response = self.client.get(
            reverse("history"),
            {"date_from": "2025-01-01", "date_to": "2025-01-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filter_mode"], "range")
        self.assertEqual(len(response.context["time_entries"]), 1)
        self.assertAlmostEqual(response.context["total_salary"], 800.0, places=2)

    def test_junior_manager_cannot_open_employee_shifts(self):
        self._login("junior-cabinet@test.com", "jr-pass")
        response = self.client.get(
            reverse("employee_shifts", args=[self.employee.id]),
            follow=True,
        )
        self.assertContains(response, "Недостаточно прав")
