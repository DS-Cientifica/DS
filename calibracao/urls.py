from django.urls import path

from .views import pdf_calibracao, pdf_calibracao_ph

urlpatterns = [
     path("pdf/<int:calibracao_id>/", pdf_calibracao, name="pdf_calibracao"),
     path("ph/<int:pk>/pdf/", pdf_calibracao_ph, name="pdf_calibracao_ph"),
]
