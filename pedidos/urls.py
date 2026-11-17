from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    # Clientes
    path("clientes/", views.ClienteListView.as_view(), name="cliente_list"),
    path("clientes/novo/", views.ClienteCreateView.as_view(), name="cliente_create"),
    path("clientes/<int:pk>/", views.ClienteDetailView.as_view(), name="cliente_detail"),
    path("clientes/<int:pk>/editar/", views.ClienteUpdateView.as_view(), name="cliente_update"),
    path("clientes/<int:pk>/inativar/", views.ClienteSituacaoView.as_view(ativar=False), name="cliente_inativar"),
    path("clientes/<int:pk>/reativar/", views.ClienteSituacaoView.as_view(ativar=True), name="cliente_reativar"),
]
