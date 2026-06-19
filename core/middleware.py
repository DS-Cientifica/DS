from .admin_bootstrap import ensure_admin_user


class EnsureAdminUserMiddleware:
    _checked = False

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self.__class__._checked:
            try:
                ensure_admin_user()
            except Exception:
                pass
            finally:
                self.__class__._checked = True

        return self.get_response(request)
