from django.urls import path
from .views import download_pdf_proposta, enviar_proposta_email, pdf_proposta

urlpatterns = [
    path("proposta/pdf/<uuid:pk>/", pdf_proposta, name="pdf_proposta"),
    path("proposta/pdf/<uuid:pk>/download/", download_pdf_proposta, name="download_pdf_proposta"),
    path("proposta/pdf/<uuid:pk>/enviar-email/", enviar_proposta_email, name="enviar_proposta_email"),
]
