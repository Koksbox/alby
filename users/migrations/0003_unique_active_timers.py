from datetime import timedelta

from django.db import migrations, models


def close_duplicate_timers(apps, schema_editor):
    """Turn duplicate starts into consecutive intervals, retaining earned time.

    Existing closed history is untouched. For each user (or user/task), close
    each preceding open entry at the next start, with a 24h cap for shifts.
    Equal-time duplicate starts naturally have zero duration. The latest stays
    open and will subsequently follow the normal stop/expiry path.
    """
    TimeEntry = apps.get_model('users', 'TimeEntry')
    alias = schema_editor.connection.alias
    entries = TimeEntry.objects.using(alias).filter(end_time__isnull=True).order_by('start_time', 'pk')
    previous = {}
    for entry in entries.iterator():
        if entry.timer_type == 'shift':
            key = ('shift', entry.user_id)
        elif entry.timer_type == 'task' and entry.task_id:
            key = ('task', entry.user_id, entry.task_id)
        else:
            continue
        preceding = previous.get(key)
        if preceding is not None:
            end = entry.start_time
            if preceding.timer_type == 'shift':
                end = min(end, preceding.start_time + timedelta(hours=24))
            TimeEntry.objects.using(alias).filter(pk=preceding.pk).update(end_time=end)
        previous[key] = entry


class Migration(migrations.Migration):
    dependencies = [('users', '0002_customuser_last_activity_timeentry_hourly_rate_and_more')]

    operations = [
        migrations.RunPython(close_duplicate_timers, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='timeentry',
            constraint=models.UniqueConstraint(
                fields=('user',), condition=models.Q(timer_type='shift', end_time__isnull=True),
                name='one_open_employee_shift',
            ),
        ),
        migrations.AddConstraint(
            model_name='timeentry',
            constraint=models.UniqueConstraint(
                fields=('user', 'task'),
                condition=models.Q(timer_type='task', end_time__isnull=True, task__isnull=False),
                name='one_open_user_task_timer',
            ),
        ),
    ]
