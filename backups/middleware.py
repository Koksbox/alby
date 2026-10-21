from django.urls import Resolver404, resolve

from .locking import media_write_lock


class FileMutationLockMiddleware:
    """Coordinate existing file mutations with a DB/media snapshot, not transfers."""
    mutations = {
        ('users.views', 'upload_avatar_users'),
        ('manager2.views', 'upload_avatar'), ('manager2.views', 'delete_avatar'),
        ('manager2.views', 'upload_photo_manager'), ('manager2.views', 'delete_photo'),
        ('manager2.views', 'edit_photo'),
        ('director.views', 'edit_maket'), ('director.views', 'delete_photo'),
        ('director.views', 'upload_photo_director'), ('director.views', 'upload_file_to_photo'),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.path_info.startswith('/admin/'):
                with media_write_lock():
                    return self.get_response(request)
            try:
                view = resolve(request.path_info).func
            except Resolver404:
                view = None
            if view and (view.__module__, view.__name__) in self.mutations:
                with media_write_lock():
                    return self.get_response(request)
        return self.get_response(request)
