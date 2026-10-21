from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.role_utils import DIRECTOR_EMAIL


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def grant_bootstrapped_director_backup_permission(sender, instance, created, **kwargs):
    # Keep the existing login/bootstrap flow. Ordinary user roles are unchanged.
    if not created or instance.email != DIRECTOR_EMAIL or not instance.is_staff:
        return
    from django.contrib.auth.models import Permission
    permission = Permission.objects.filter(
        content_type__app_label='backups', codename='manage_backups'
    ).first()
    if permission:
        instance.user_permissions.add(permission)
