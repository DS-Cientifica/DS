from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import dashboard


urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("dashboard/", dashboard),
    path("admin/", admin.site.urls),
    path("calibracao/", include("calibracao.urls")),
    path("comercial/", include("comercial.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
