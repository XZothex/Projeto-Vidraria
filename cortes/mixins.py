from django.contrib.auth.mixins import LoginRequiredMixin


class AcessoCortesMixin(LoginRequiredMixin):
    """Ponto de integração para as permissões definidas pela etapa 2."""
