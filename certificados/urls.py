from django.urls import path
from .views import baixar_certificado, consultar_certificado

app_name = "certificados"
urlpatterns = [
    path("verificar/<uuid:uuid_publico>/", consultar_certificado, name="consulta"),
    path("verificar/<uuid:uuid_publico>/arquivo/", baixar_certificado, name="download"),
]
