from django.conf import settings
from django.http import HttpResponseNotFound


class PublicCertificateHostMiddleware:
    """Restringe o host público à consulta de certificados e etiquetas."""

    allowed_prefixes = ("/verificar/", "/etiquetas/")
    allowed_paths = ("/static/img/logo_ds.png",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":", 1)[0].lower().rstrip(".")
        hosts_publicos = {
            item.lower().rstrip(".")
            for item in getattr(settings, "PUBLIC_CERTIFICATE_HOSTS", ())
        }
        host_publico = host in hosts_publicos

        caminho_permitido = (
            request.path in self.allowed_paths
            or request.path.startswith(self.allowed_prefixes)
        )
        if host_publico and not caminho_permitido:
            return self._proteger(HttpResponseNotFound("Página não encontrada."))

        response = self.get_response(request)
        if host_publico:
            self._proteger(response)
        return response

    @staticmethod
    def _proteger(response):
        response["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response["Referrer-Policy"] = "no-referrer"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response["Cache-Control"] = "private, no-store"
        return response
