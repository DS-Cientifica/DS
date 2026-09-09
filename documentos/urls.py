from django.urls import path
from .views import download_documento

app_name = "documentos"
urlpatterns = [path("<uuid:pk>/download/", download_documento, name="download")]
