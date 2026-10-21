from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from manager2.models import Photo, Task, TimeManger
from users.models import TimeEntry
from users.timers import change_shift, change_task_timer

User = get_user_model()


class TimerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='timer@test.com', password='pass', full_name='Timer',
            is_active=True, post_user='employee',
        )
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.client.force_login(self.user)
        self.photo = Photo.objects.create(image='photos/test.jpg', image_name='Test')
        self.task = Task.objects.create(photo=self.photo, title='Task', description='Test')
        self.task.submitted_by.add(self.user)

    def test_all_employee_start_endpoints_are_idempotent(self):
        for name in ('start_timer1', 'api_start_timer', 'api_start_timer'):
            self.assertIn(self.client.post(reverse(name)).status_code, (200, 302))
        self.assertEqual(TimeEntry.objects.filter(user=self.user, timer_type='shift', end_time=None).count(), 1)
        self.client.post(reverse('api_stop_timer'))
        self.client.post(reverse('api_stop_timer'))
        self.assertFalse(TimeEntry.objects.filter(user=self.user, timer_type='shift', end_time=None).exists())

    def test_repeated_explicit_toggle_action_does_not_stop_new_shift(self):
        self.client.post(reverse('toggle_timer'), {'timer_action': 'start'})
        self.client.post(reverse('toggle_timer'), {'timer_action': 'start'})
        self.assertEqual(TimeEntry.objects.filter(user=self.user, timer_type='shift', end_time=None).count(), 1)

    def test_database_rejects_duplicate_employee_and_manager_shifts(self):
        change_shift(self.user, 'start')
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeEntry.objects.create(user=self.user, timer_type='shift', start_time=timezone.now())
        change_shift(self.user, 'start', manager=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeManger.objects.create(manager=self.user, start_time=timezone.now())

    def test_manager_repeated_start_and_stop_are_idempotent(self):
        for _ in range(2):
            response = self.client.post(reverse('start_timer_manager'))
            self.assertEqual(response.status_code, 302)
        self.assertEqual(TimeManger.objects.filter(manager=self.user, end_time=None).count(), 1)
        for _ in range(2):
            self.client.post(reverse('stop_timer_manager'))
        self.assertFalse(TimeManger.objects.filter(manager=self.user, end_time=None).exists())

    def test_shift_rate_stays_at_start_rate(self):
        employee, _ = change_shift(self.user, 'start')
        manager, _ = change_shift(self.user, 'start', manager=True)
        self.user.big_stavka = 999
        self.user.save(update_fields=['big_stavka'])
        change_shift(self.user, 'stop')
        change_shift(self.user, 'stop', manager=True)
        employee.refresh_from_db()
        manager.refresh_from_db()
        self.assertEqual(employee.hourly_rate, 140)
        self.assertEqual(manager.hourly_rate, 140)

    @override_settings(TIME_TRACKER_SHIFT_MAX_SECONDS=3600, TIME_TRACKER_MANAGER_MAX_SECONDS=3600)
    def test_overdue_stop_caps_duration_and_does_not_reopen(self):
        started = timezone.now() - timedelta(hours=3)
        shift = TimeEntry.objects.create(user=self.user, timer_type='shift', start_time=started)
        manager = TimeManger.objects.create(manager=self.user, start_time=started)
        response = self.client.post(reverse('api_stop_timer'))
        self.assertEqual(response.status_code, 200)
        self.client.post(reverse('stop_timer_manager'))
        shift.refresh_from_db()
        manager.refresh_from_db()
        self.assertEqual(shift.end_time, started + timedelta(hours=1))
        self.assertEqual(manager.end_time, started + timedelta(hours=1))
        self.assertFalse(TimeEntry.objects.filter(user=self.user, end_time=None).exists())
        self.assertFalse(TimeManger.objects.filter(manager=self.user, end_time=None).exists())

    def test_stale_stop_does_not_close_newer_shift(self):
        first, _ = change_shift(self.user, 'start')
        change_shift(self.user, 'stop')
        second, _ = change_shift(self.user, 'start')
        self.client.post(reverse('api_stop_timer'), {'entry_id': first.pk})
        second.refresh_from_db()
        self.assertIsNone(second.end_time)

    def test_task_timer_repeat_start_is_unique_and_unpaid(self):
        for _ in range(2):
            self.client.post(reverse('start_timer', args=[self.task.pk]))
        entries = TimeEntry.objects.filter(user=self.user, task=self.task, end_time=None)
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.get().hourly_rate, 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeEntry.objects.create(user=self.user, task=self.task, timer_type='task', start_time=timezone.now())

    def test_task_page_uses_database_not_stale_session(self):
        entry, _ = change_task_timer(self.user, self.task, 'start')
        session = self.client.session
        session['timer_running'] = False
        session.save()
        response = self.client.get(reverse('work_on_task', args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session['timer_running'])
        self.assertContains(response, 'stopTimerForm')
        self.assertNotContains(response, 'id="startTimerForm"')

    def test_submission_closes_task_timer_but_keeps_shift_open(self):
        shift, _ = change_shift(self.user, 'start')
        task_timer, _ = change_task_timer(self.user, self.task, 'start')
        response = self.client.post(reverse('work_on_task', args=[self.task.pk]), {'zadaha': 'complete'})
        self.assertEqual(response.status_code, 302)
        task_timer.refresh_from_db()
        shift.refresh_from_db()
        self.assertIsNotNone(task_timer.end_time)
        self.assertIsNone(shift.end_time)
        self.assertFalse(self.client.session['timer_running'])

    def test_first_participant_can_choose_another_task_after_submission(self):
        colleague = User.objects.create_user(
            email='colleague@test.com', full_name='Colleague', is_active=True, post_user='employee',
        )
        self.task.submitted_by.add(colleague)
        other = Task.objects.create(photo=self.photo, title='Another task', description='Next')
        self.client.post(reverse('work_on_task', args=[self.task.pk]), {'zadaha': 'complete'})
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_submitted_for_review)
        response = self.client.get(reverse('select_task', args=[self.photo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['tasks']), [other])
        response = self.client.get(reverse('startapp'))
        self.assertIsNone(response.context['active_task'])
        response = self.client.get(reverse('photo_maket'))
        self.assertIsNone(response.context['active_task'])
        response = self.client.post(reverse('select_task', args=[self.photo.pk]), {'task_id': other.pk})
        self.assertRedirects(response, reverse('work_on_task', args=[other.pk]))

    def test_task_start_does_not_admit_nonparticipant(self):
        self.task.submitted_by.remove(self.user)
        response = self.client.post(reverse('start_timer', args=[self.task.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TimeEntry.objects.filter(user=self.user, task=self.task).exists())


class ConcurrentTimerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='race@test.com', full_name='Race', is_active=True, post_user='employee')

    def test_concurrent_start_creates_only_one_shift(self):
        barrier = Barrier(2)
        def start():
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=5)
                return change_shift(user, 'start')[0].pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: start(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(TimeEntry.objects.filter(user=self.user, end_time=None).count(), 1)


class DuplicateTimerMigrationTests(TransactionTestCase):
    """Upgrade real old-schema data, including starts the old APIs duplicated."""

    migrate_from = [
        ('users', '0002_customuser_last_activity_timeentry_hourly_rate_and_more'),
        ('manager2', '0003_timemanger_hourly_rate_alter_task_photo'),
    ]
    migrate_to = [
        ('users', '0003_unique_active_timers'),
        ('manager2', '0004_unique_active_manager_shift'),
    ]

    def setUp(self):
        executor = MigrationExecutor(connection)
        self.latest_targets = executor.loader.graph.leaf_nodes()
        self.addCleanup(self.restore_latest)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from).apps

    def restore_latest(self):
        MigrationExecutor(connection).migrate(self.latest_targets)

    def test_duplicate_upgrade_preserves_earned_time_rates_and_closed_history(self):
        OldUser = self.old_apps.get_model('users', 'CustomUser')
        OldTimeEntry = self.old_apps.get_model('users', 'TimeEntry')
        OldManagerTime = self.old_apps.get_model('manager2', 'TimeManger')
        OldPhoto = self.old_apps.get_model('manager2', 'Photo')
        OldTask = self.old_apps.get_model('manager2', 'Task')
        user = OldUser.objects.create(email='migration@test.com', full_name='Migration')
        late_user = OldUser.objects.create(email='long-migration@test.com', full_name='Long shift')
        nine = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        ten = nine + timedelta(hours=1)
        eleven = ten + timedelta(hours=1)
        closed_start = nine - timedelta(hours=2)
        closed_end = nine - timedelta(hours=1)
        closed = OldTimeEntry.objects.create(
            user=user, timer_type='shift', start_time=closed_start, end_time=closed_end, hourly_rate=130,
        )
        first = OldTimeEntry.objects.create(user=user, timer_type='shift', start_time=nine, hourly_rate=140)
        second = OldTimeEntry.objects.create(user=user, timer_type='shift', start_time=ten, hourly_rate=160)
        simultaneous = OldTimeEntry.objects.create(user=user, timer_type='shift', start_time=eleven, hourly_rate=180)
        latest = OldTimeEntry.objects.create(user=user, timer_type='shift', start_time=eleven, hourly_rate=200)
        long_shift = OldTimeEntry.objects.create(user=late_user, timer_type='shift', start_time=nine, hourly_rate=120)
        OldTimeEntry.objects.create(user=late_user, timer_type='shift', start_time=nine + timedelta(hours=30), hourly_rate=125)

        manager_closed = OldManagerTime.objects.create(manager=user, start_time=closed_start, end_time=closed_end, hourly_rate=190)
        manager_first = OldManagerTime.objects.create(manager=user, start_time=nine, hourly_rate=200)
        manager_latest = OldManagerTime.objects.create(manager=user, start_time=ten, hourly_rate=225)
        manager_long = OldManagerTime.objects.create(manager=late_user, start_time=nine, hourly_rate=180)
        OldManagerTime.objects.create(manager=late_user, start_time=nine + timedelta(hours=30), hourly_rate=185)

        photo = OldPhoto.objects.create(image='photos/test.jpg', image_name='Migration')
        task = OldTask.objects.create(photo=photo, title='Migration task', description='Test')
        task_first = OldTimeEntry.objects.create(user=user, task=task, timer_type='task', start_time=nine, hourly_rate=0)
        task_latest = OldTimeEntry.objects.create(user=user, task=task, timer_type='task', start_time=nine + timedelta(hours=30), hourly_rate=0)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        Entries = new_apps.get_model('users', 'TimeEntry')
        ManagerEntries = new_apps.get_model('manager2', 'TimeManger')
        first.refresh_from_db()
        second.refresh_from_db()
        simultaneous.refresh_from_db()
        latest.refresh_from_db()
        closed.refresh_from_db()
        long_shift.refresh_from_db()
        manager_first.refresh_from_db()
        manager_latest.refresh_from_db()
        manager_closed.refresh_from_db()
        manager_long.refresh_from_db()
        task_first.refresh_from_db()
        task_latest.refresh_from_db()

        self.assertEqual(first.end_time, ten)
        self.assertEqual(second.end_time, eleven)
        self.assertEqual(simultaneous.end_time, eleven)
        self.assertIsNone(latest.end_time)
        self.assertEqual(first.hourly_rate, 140)
        self.assertEqual(second.hourly_rate, 160)
        earned = sum(
            (entry.end_time - entry.start_time).total_seconds() / 3600 * entry.hourly_rate
            for entry in (first, second)
        )
        self.assertEqual(earned, 300)
        self.assertEqual(long_shift.end_time, nine + timedelta(hours=24))
        self.assertEqual((closed.start_time, closed.end_time, closed.hourly_rate), (closed_start, closed_end, 130))
        self.assertEqual(manager_first.end_time, ten)
        self.assertEqual(manager_first.hourly_rate, 200)
        self.assertIsNone(manager_latest.end_time)
        self.assertEqual(manager_long.end_time, nine + timedelta(hours=24))
        self.assertEqual((manager_closed.start_time, manager_closed.end_time, manager_closed.hourly_rate), (closed_start, closed_end, 190))
        self.assertEqual(task_first.end_time, nine + timedelta(hours=30))
        self.assertIsNone(task_latest.end_time)
        self.assertEqual(Entries.objects.filter(user_id=user.pk, timer_type='shift', end_time=None).count(), 1)
        self.assertEqual(ManagerEntries.objects.filter(manager_id=user.pk, end_time=None).count(), 1)
        self.assertEqual(Entries.objects.filter(user_id=user.pk, task_id=task.pk, end_time=None).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Entries.objects.create(user_id=user.pk, timer_type='shift', start_time=eleven)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ManagerEntries.objects.create(manager_id=user.pk, start_time=eleven)
