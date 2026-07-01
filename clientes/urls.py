from django.urls import path

from .views import consultar_cnpj


urlpatterns = [
    path("api/cnpj/<str:cnpj>/", consultar_cnpj, name="clientes_consultar_cnpj"),
]
