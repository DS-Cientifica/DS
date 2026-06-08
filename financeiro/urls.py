from django.urls import path

from .views import pedido_compra_duplicar, pedido_compra_pdf

app_name = "financeiro"

urlpatterns = [
    path("pedido-compra/<uuid:pk>/pdf/", pedido_compra_pdf, name="pedido_compra_pdf"),
    path("pedido-compra/<uuid:pk>/duplicar/", pedido_compra_duplicar, name="pedido_compra_duplicar"),
]
