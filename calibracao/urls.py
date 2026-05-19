from django.urls import path
from .views import pdf_calibracao

urlpatterns = [
     path("pdf/<int:calibracao_id>/", pdf_calibracao, name="pdf_calibracao")

]

