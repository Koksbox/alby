from django.conf import settings
from django.db import migrations


def grant_permission(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    alias = schema_editor.connection.alias
    content_type, _ = ContentType.objects.using(alias).get_or_create(app_label='backups', model='backuprun')
    permission, _ = Permission.objects.using(alias).get_or_create(
        content_type=content_type, codename='manage_backups',
        defaults={'name': 'Can manage backups'},
    )
    director = User.objects.using(alias).filter(email='albygroup@bk.ru').first()
    if director:
        director.user_permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ('backups', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [migrations.RunPython(grant_permission, migrations.RunPython.noop)]
