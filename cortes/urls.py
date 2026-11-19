from django.urls import path
from . import views

app_name = "cortes"
urlpatterns = [
    path("", views.CortesHomeView.as_view(), name="lista"),
    path("novo/", views.OperacaoCreateView.as_view(), name="novo"),
    path("<int:pk>/", views.OperacaoDetailView.as_view(), name="detalhe"),
    path("chapas/", views.ChapaListView.as_view(), name="chapas"),
    path("chapas/nova/", views.ChapaCreateView.as_view(), name="chapa_nova"),
]
