from datetime import timedelta

from django.db import migrations, models


def close_duplicate_shifts(apps, schema_editor):
    TimeManger = apps.get_model('manager2', 'TimeManger')
    alias = schema_editor.connection.alias
    previous = {}
    for entry in TimeManger.objects.using(alias).filter(end_time__isnull=True).order_by('start_time', 'pk').iterator():
        preceding = previous.get(entry.manager_id)
        if preceding is not None:
            end = min(entry.start_time, preceding.start_time + timedelta(hours=24))
            TimeManger.objects.using(alias).filter(pk=preceding.pk).update(end_time=end)
        previous[entry.manager_id] = entry


class Migration(migrations.Migration):
    dependencies = [('manager2', '0003_timemanger_hourly_rate_alter_task_photo')]

    operations = [
        migrations.RunPython(close_duplicate_shifts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='timemanger',
            constraint=models.UniqueConstraint(
                fields=('manager',), condition=models.Q(end_time__isnull=True),
                name='one_open_manager_shift',
            ),
        ),
    ]
