import datetime as dt

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import TimeEntry

User = get_user_model()


class EmployeeOwnShiftHistoryTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")
        self.employee = User.objects.create_user(
            email="shift-owner@test.com",
            password="emp-pass",
            full_name="Shift Owner",
            phone_number="7777777777",
            post_user="employee",
            is_active=True,
        )
        self.client.post(
            reverse("login"),
            {"email": "shift-owner@test.com", "password": "emp-pass"},
        )

    def test_money_filters_own_shifts_by_date_range(self):
        jan_start = timezone.make_aware(dt.datetime(2025, 1, 12, 9, 0, 0))
        jan_end = timezone.make_aware(dt.datetime(2025, 1, 12, 13, 0, 0))
        feb_start = timezone.make_aware(dt.datetime(2025, 2, 12, 9, 0, 0))
        feb_end = timezone.make_aware(dt.datetime(2025, 2, 12, 13, 0, 0))

        TimeEntry.objects.create(
            user=self.employee,
            timer_type="shift",
            start_time=jan_start,
            end_time=jan_end,
        )
        TimeEntry.objects.create(
            user=self.employee,
            timer_type="shift",
            start_time=feb_start,
            end_time=feb_end,
        )

        response = self.client.get(
            reverse("money"),
            {"date_from": "2025-01-01", "date_to": "2025-01-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filter_mode"], "range")
        self.assertEqual(len(response.context["time_entries_shift"]), 1)
        self.assertContains(response, 'name="date_from"')
        self.assertContains(response, 'name="date_to"')
        # 4 часа * ставка employee (140)
        self.assertAlmostEqual(
            response.context["total_salary_shift_completed"], 560.0, places=2
        )
