from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from .home_views import inicio
from .calendar_views import calendario_integrado
from .views import dashboard


urlpatterns = [
    path("", inicio, name="inicio"),
    path("inicio/", inicio),
    path("dashboard/", dashboard, name="dashboard"),
    path("calendario/", calendario_integrado, name="calendario_integrado"),
    path("admin/", admin.site.urls),
    path("clientes/", include("clientes.urls")),
    path("calibracao/", include("calibracao.urls")),
    path("comercial/", include("comercial.urls")),
    path("financeiro/", include("financeiro.urls")),
    path("documentos/", include("documentos.urls")),
    path("", include("certificados.urls")),
]


if settings.DEBUG and not getattr(settings, "USE_CLOUD_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif not getattr(settings, "USE_CLOUD_MEDIA", False):
    urlpatterns += [
        re_path(
            rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]
