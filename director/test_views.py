import datetime as dt

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from manager2.models import TimeManger
from users.role_utils import DIRECTOR_EMAIL
from users.views import DIRECTOR_PASSWORD

User = get_user_model()


class DirectorShiftViewsTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")
        self.manager = User.objects.create_user(
            email="manager-shift@test.com",
            password="mgr-pass",
            full_name="Manager Shift",
            phone_number="3333333333",
            post_user="manager",
            is_active=True,
        )
        self.client.post(
            reverse("login"),
            {"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD},
        )

    def _create_shift(self, start, end):
        return TimeManger.objects.create(
            manager=self.manager,
            start_time=start,
            end_time=end,
        )

    def test_manager_shifts_filters_by_date_range(self):
        in_range_start = timezone.make_aware(dt.datetime(2025, 1, 10, 9, 0, 0))
        in_range_end = timezone.make_aware(dt.datetime(2025, 1, 10, 13, 0, 0))
        out_range_start = timezone.make_aware(dt.datetime(2025, 2, 10, 9, 0, 0))
        out_range_end = timezone.make_aware(dt.datetime(2025, 2, 10, 13, 0, 0))

        self._create_shift(in_range_start, in_range_end)
        self._create_shift(out_range_start, out_range_end)

        response = self.client.get(
            reverse("manager_shifts", args=[self.manager.id]),
            {"date_from": "2025-01-01", "date_to": "2025-01-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filter_mode"], "range")
        self.assertEqual(len(response.context["time_entries"]), 1)
        self.assertAlmostEqual(response.context["total_salary"], 800.0, places=2)
