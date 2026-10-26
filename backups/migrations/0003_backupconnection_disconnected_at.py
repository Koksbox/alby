from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('backups', '0002_director_backup_permission')]

    operations = [
        migrations.AddField(
            model_name='backupconnection',
            name='disconnected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
