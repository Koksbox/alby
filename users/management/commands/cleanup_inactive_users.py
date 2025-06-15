from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Удаляет неактивированных пользователей, у которых истек срок действия кода подтверждения'

    def handle(self, *args, **options):
        try:
            # Получаем всех неактивированных пользователей
            inactive_users = CustomUser.objects.filter(is_active=False)
            deleted_count = 0

            for user in inactive_users:
                if user.should_be_deleted():
                    user.delete()
                    deleted_count += 1
                    logger.info(f'Удален неактивированный пользователь: {user.email}')

            self.stdout.write(
                self.style.SUCCESS(f'Успешно удалено {deleted_count} неактивированных пользователей')
            )
        except Exception as e:
            logger.error(f'Ошибка при удалении неактивированных пользователей: {str(e)}')
            self.stdout.write(
                self.style.ERROR(f'Произошла ошибка: {str(e)}')
            ) 