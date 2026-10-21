import datetime as dt
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from manager2.models import TimeManger
from users.models import TimeEntry
from users.role_utils import DIRECTOR_EMAIL, get_month_period, get_salary_period, get_shift_period
from users.reporting import shift_history_context

User = get_user_model()


def local(value):
    return timezone.make_aware(dt.datetime.fromisoformat(value))


class ReportingPeriodTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client(HTTP_HOST="127.0.0.1")
        self.employee = User.objects.create_user(
            email="report-employee@test.com", password="password", full_name="Employee",
            post_user="employee", is_active=True,
        )
        self.manager = User.objects.create_user(
            email="report-manager@test.com", password="password", full_name="Manager",
            post_user="manager", is_active=True,
        )
        self.director = User.objects.create_user(
            email=DIRECTOR_EMAIL, password="password", full_name="Director", is_active=True,
        )

    def employee_shift(self):
        return TimeEntry.objects.create(
            user=self.employee, timer_type="shift", hourly_rate=140,
            start_time=local("2025-01-31T22:00:00"), end_time=local("2025-02-01T06:00:00"),
        )

    def test_employee_night_shift_matches_history_director_report_and_statistics(self):
        self.employee_shift()
        self.employee.big_stavka = 300
        self.employee.save(update_fields=["big_stavka"])
        self.client.force_login(self.employee)
        own = self.client.get(reverse("money"), {"month": "2025-01"})
        statistics = self.client.get(reverse("statistic"), {"month": "2025-01"})
        self.assertEqual(own.context["total_salary_shift_completed"], 1120)
        self.assertEqual(statistics.context["total_salary"], 1120)
        self.assertEqual(statistics.context["total_shift_hours"], 8)
        feb = self.client.get(reverse("money"), {"month": "2025-02"})
        self.assertEqual(feb.context["total_salary_shift_completed"], 0)
        self.client.force_login(self.director)
        report = self.client.get(reverse("salary_report"), {
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.context["individual_salaries"][self.employee.pk], 1120)
        self.assertEqual(report.context["total_salary"], 1120)
        stats = self.client.get(reverse("director_user_statistic", args=[self.employee.pk]),
                                {"month": "2025-01"})
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.context["total_salary"], 1120)

    def test_manager_night_shift_matches_history_report_and_statistics(self):
        TimeManger.objects.create(
            manager=self.manager, hourly_rate=200,
            start_time=local("2025-01-31T22:00:00"), end_time=local("2025-02-01T06:00:00"),
        )
        self.manager.big_stavka = 400
        self.manager.save(update_fields=["big_stavka"])
        self.client.force_login(self.manager)
        history = self.client.get(reverse("history"), {"month": "2025-01"})
        self.assertEqual(history.context["total_salary"], 1600)
        own_stats = self.client.get(reverse("my_statistic"), {"month": "2025-01"})
        self.assertEqual(own_stats.context["total_salary"], 1600)
        self.client.force_login(self.director)
        report = self.client.get(reverse("salary_manager"), {
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.context["individual_salaries"][self.manager.pk], 1600)
        director_stats = self.client.get(reverse("director_manager_statistic", args=[self.manager.pk]),
                                         {"month": "2025-01"})
        self.assertEqual(director_stats.status_code, 200)
        self.assertEqual(director_stats.context["user"].pk, self.manager.pk)
        self.assertEqual(director_stats.context["total_salary"], 1600)

    def test_local_month_starts_at_local_midnight_even_near_utc_month_boundary(self):
        now = local("2025-03-01T00:30:00").astimezone(dt.timezone.utc)
        with patch("django.utils.timezone.now", return_value=now):
            start, end = get_month_period(self.factory.get("/"))
        self.assertEqual(start, local("2025-03-01T00:00:00"))
        self.assertEqual(end, local("2025-04-01T00:00:00"))

    def test_invalid_incomplete_and_extreme_periods_never_crash(self):
        for params in ({"start_date": "2025-01-31"}, {"end_date": "2025-01-31"},
                       {"start_date": "2025-99-99", "end_date": "2025-02-30"},
                       {"start_date": "9999-12-31"}, {"end_date": "9999-12-31"},
                       {"start_date": "2025-02-01", "end_date": "2025-01-01"}):
            with self.subTest(params=params):
                start, end, _, _ = get_salary_period(self.factory.get("/", params))
                self.assertTrue(timezone.is_aware(start))
                self.assertGreater(end, start)
        for params in ({"date_from": "2025-02-30", "date_to": "2025-03-10"},
                       {"date_from": "2025-01-01", "date_to": "9999-12-31"},
                       {"month": "9999-12"}):
            start, end, *_ = get_shift_period(self.factory.get("/", params))
            self.assertGreater(end, start)

    def test_active_shift_preview_uses_saved_rate_and_start_period(self):
        now = local("2025-02-01T03:00:00")
        TimeManger.objects.create(manager=self.manager, hourly_rate=175,
                                   start_time=local("2025-01-31T22:00:00"))
        with patch("django.utils.timezone.now", return_value=now):
            january = shift_history_context(self.factory.get("/", {"month": "2025-01"}),
                                             self.manager, manager=True)
            february = shift_history_context(self.factory.get("/", {"month": "2025-02"}),
                                              self.manager, manager=True)
        self.assertEqual(january["total_salary"], 875)
        self.assertEqual(january["user_stavka"], 175)
        self.assertTrue(january["active_shift_preview"]["included"])
        self.assertEqual(february["total_salary"], 0)
        self.assertFalse(february["active_shift_preview"]["included"])

    def test_director_reports_accept_incomplete_date_fields(self):
        self.client.force_login(self.director)
        for route in ("salary_report", "salary_manager"):
            for params in ({"start_date": "2025-01-10"}, {"end_date": "bad"}):
                self.assertEqual(self.client.get(reverse(route), params).status_code, 200)

    def test_history_and_report_preserve_fractional_seconds_in_salary(self):
        start = local("2025-01-10T09:00:00")
        TimeEntry.objects.create(user=self.employee, timer_type="shift", hourly_rate=3600,
                                 start_time=start, end_time=start + dt.timedelta(seconds=1.5))
        context = shift_history_context(self.factory.get("/", {"month": "2025-01"}), self.employee)
        self.assertEqual(context["total_salary"], 1.5)
        self.assertEqual(context["active_shift_preview"]["base_salary"], 1.5)
