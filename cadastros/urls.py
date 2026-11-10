from django.urls import path

from . import views

app_name = "cadastros"

urlpatterns = [
    # Materiais
    path("materiais/", views.MaterialListView.as_view(), name="material_list"),
    path("materiais/novo/", views.MaterialCreateView.as_view(), name="material_create"),
    path("materiais/<int:pk>/", views.MaterialDetailView.as_view(), name="material_detail"),
    path("materiais/<int:pk>/editar/", views.MaterialUpdateView.as_view(), name="material_update"),
    path("materiais/<int:pk>/inativar/", views.MaterialInativarView.as_view(), name="material_inativar"),
    path("materiais/<int:pk>/reativar/", views.MaterialReativarView.as_view(), name="material_reativar"),
    # Fornecedores
    path("fornecedores/", views.FornecedorListView.as_view(), name="fornecedor_list"),
    path("fornecedores/novo/", views.FornecedorCreateView.as_view(), name="fornecedor_create"),
    path("fornecedores/<int:pk>/", views.FornecedorDetailView.as_view(), name="fornecedor_detail"),
    path("fornecedores/<int:pk>/editar/", views.FornecedorUpdateView.as_view(), name="fornecedor_update"),
    path("fornecedores/<int:pk>/inativar/", views.FornecedorInativarView.as_view(), name="fornecedor_inativar"),
    path("fornecedores/<int:pk>/reativar/", views.FornecedorReativarView.as_view(), name="fornecedor_reativar"),
]
