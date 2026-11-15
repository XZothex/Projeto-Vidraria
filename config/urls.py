from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Login/logout PROVISÓRIOS com as views padrão do Django.
    # Substituir pelas rotas do módulo de login quando ele existir.
    path("entrar/", auth_views.LoginView.as_view(), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    # Módulo de cadastros (materiais e fornecedores)
    path("cadastros/", include("cadastros.urls")),
    # Página inicial provisória (o dashboard é de outro módulo)
    path("", RedirectView.as_view(pattern_name="cadastros:material_list"), name="home"),
]
