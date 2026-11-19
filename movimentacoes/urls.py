from django.urls import path

from . import views

app_name = "movimentacoes"

urlpatterns = [
    path("", views.LotesView.as_view(), name="lotes"),
    path("historico/", views.HistoricoView.as_view(), name="historico"),
    path("entrada/", views.EntradaView.as_view(), name="entrada"),
    path("perda/", views.PerdaView.as_view(), name="perda"),
    path("ajuste/", views.AjusteView.as_view(), name="ajuste"),
]
