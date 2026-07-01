from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from .views import dashboard


urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("dashboard/", dashboard),
    path("admin/", admin.site.urls),
    path("clientes/", include("clientes.urls")),
    path("calibracao/", include("calibracao.urls")),
    path("comercial/", include("comercial.urls")),
    path("financeiro/", include("financeiro.urls")),
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
