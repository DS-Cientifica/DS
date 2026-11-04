from django.urls import path
from .views import baixar_certificado, consultar_certificado, consultar_etiqueta

app_name = "certificados"
urlpatterns = [
    path("etiquetas/<uuid:token_publico>/", consultar_etiqueta, name="consulta_etiqueta"),
    path("verificar/<uuid:uuid_publico>/", consultar_certificado, name="consulta"),
    path("verificar/<uuid:uuid_publico>/arquivo/", baixar_certificado, name="download"),
]
