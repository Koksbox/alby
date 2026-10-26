"""Detach Disk without deleting tokens, settings, history or backup files."""
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backups.locking import backup_lock
from backups.models import BackupConnection


class Command(BaseCommand):
    help = 'Detach Yandex Disk until a new connection is authorized. Preserve tokens, .env, passwords, archives and backup history.'

    def handle(self, *args, **options):
        try:
            # The worker holds this lock during upload/rotation as well.
            with backup_lock(blocking=False):
                with transaction.atomic():
                    connection, _ = BackupConnection.objects.get_or_create(pk=1)
                    if connection.disconnected_at is None:
                        connection.disconnected_at = timezone.now()
                        connection.save(update_fields=['disconnected_at'])
                    # Keep logins; cancel only unfinished OAuth requests.
                    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
                        data = session.get_decoded()
                        if 'yandex_backup_oauth' in data:
                            del data['yandex_backup_oauth']
                            session.session_data = Session.get_session_store_class()().encode(data)
                            session.save(update_fields=['session_data'])
        except BlockingIOError:
            raise CommandError('A backup is running. Retry after it finishes, or stop the worker first.') from None
        self.stdout.write(self.style.SUCCESS(
            'Yandex Disk detached. Tokens, .env, application secrets, passwords, archives and history preserved. '
            'The worker will wait for a new authorized connection. Permission in the Yandex account is unchanged.'
        ))
