from users.role_utils import is_director


def backup_status(request):
    match = getattr(request, 'resolver_match', None)
    if (match and match.url_name == 'home_director' and is_director(request.user)
            and request.user.has_perm('backups.manage_backups')):
        from .views import connection_status
        return {'backup_status': connection_status()}
    return {}
