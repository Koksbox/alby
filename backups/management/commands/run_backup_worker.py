import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from backups.engine import run_due_backup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run scheduled database/media backups; --once checks the schedule once.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                result = run_due_backup()
                if result:
                    self.stdout.write('Backup %s: %s' % (result.id, result.status))
            except KeyboardInterrupt:
                return
            except Exception as exc:
                # Exception text could contain credentials; only log the class.
                logger.error('Backup worker check failed (%s).', type(exc).__name__)
                if options['once']:
                    raise
            finally:
                close_old_connections()
            if options['once']:
                return
            time.sleep(max(1, getattr(settings, 'BACKUP_POLL_SECONDS', 30)))
