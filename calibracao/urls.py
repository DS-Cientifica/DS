from django.urls import path

from .ajax_views import ordem_servico_do_instrumento
from .views import (
    pdf_calibracao,
    pdf_calibracao_dispositivo_seguranca,
    pdf_calibracao_esfigmomanometro,
    pdf_calibracao_ph,
)

urlpatterns = [
     path(
         "ajax/ordem-servico-instrumento/",
         ordem_servico_do_instrumento,
         name="ordem_servico_do_instrumento",
     ),
     path("pdf/<int:calibracao_id>/", pdf_calibracao, name="pdf_calibracao"),
     path("ph/<int:pk>/pdf/", pdf_calibracao_ph, name="pdf_calibracao_ph"),
     path(
         "dispositivo-seguranca/<uuid:pk>/certificado/",
         pdf_calibracao_dispositivo_seguranca,
         name="pdf_calibracao_dispositivo_seguranca",
     ),
     path(
         "esfigmomanometro/<uuid:pk>/certificado/",
         pdf_calibracao_esfigmomanometro,
         name="pdf_calibracao_esfigmomanometro",
     ),
]
