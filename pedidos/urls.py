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
    # Pedidos
    path("", views.PedidoListView.as_view(), name="pedido_list"),
    path("novo/", views.PedidoCreateView.as_view(), name="pedido_create"),
    path("<int:pk>/", views.PedidoDetailView.as_view(), name="pedido_detail"),
    path("<int:pk>/editar/", views.PedidoUpdateView.as_view(), name="pedido_update"),
    path("<int:pk>/reservar/", views.PedidoReservarView.as_view(), name="pedido_reservar"),
    path("<int:pk>/liberar/", views.PedidoLiberarView.as_view(), name="pedido_liberar"),
    path("<int:pk>/cancelar/", views.PedidoCancelarView.as_view(), name="pedido_cancelar"),
    path("<int:pk>/entregar/", views.PedidoEntregarView.as_view(), name="pedido_entregar"),
    # Itens
    path("<int:pedido_pk>/itens/novo/", views.ItemCreateView.as_view(), name="item_create"),
    path("<int:pedido_pk>/itens/<int:pk>/editar/", views.ItemUpdateView.as_view(), name="item_update"),
    path("<int:pk>/itens/<int:item_pk>/remover/", views.ItemRemoverView.as_view(), name="item_remover"),
    path("<int:pk>/itens/<int:item_pk>/reservar/", views.ItemReservarView.as_view(), name="item_reservar"),
    path("<int:pk>/itens/<int:item_pk>/liberar/", views.ItemLiberarView.as_view(), name="item_liberar"),
]
