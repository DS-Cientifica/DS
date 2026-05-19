from django.urls import path
from .views import pdf_proposta

urlpatterns = [
    path("proposta/pdf/<uuid:pk>/", pdf_proposta, name="pdf_proposta"),
]