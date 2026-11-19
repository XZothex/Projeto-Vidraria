from django.urls import path

from . import views

app_name = "contas"
urlpatterns = [
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/<int:pk>/alternar-status/", views.alternar_status, name="alternar_status"),
]
