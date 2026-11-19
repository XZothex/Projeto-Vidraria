from django.urls import path
from . import views

app_name = "painel"
urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("historico/", views.HistoricoView.as_view(), name="historico"),
    path("relatorios/", views.RelatoriosView.as_view(), name="relatorios"),
    path("relatorios/<str:tipo>/", views.RelatorioView.as_view(), name="relatorio"),
]
