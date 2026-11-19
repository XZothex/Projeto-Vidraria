from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("contas/", include("contas.urls")),
    # Autenticação e sessões do Django.
    path("entrar/", auth_views.LoginView.as_view(), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    # Módulo de cadastros (materiais e fornecedores)
    path("cadastros/", include("cadastros.urls")),
    # Módulo de pedidos (clientes, pedidos, reservas e entregas)
    path("pedidos/", include("pedidos.urls")),
    # Módulo de entradas, perdas e ajustes de estoque
    path("painel/", include("painel.urls")),
    path("cortes/", include("cortes.urls")),
    path("movimentacoes/", include("movimentacoes.urls")),
    # Página inicial provisória (o dashboard é de outro módulo)
    path("", RedirectView.as_view(pattern_name="cadastros:material_list"), name="home"),
]
