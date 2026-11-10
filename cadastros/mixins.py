from django.contrib.auth.mixins import LoginRequiredMixin


class AcessoCadastrosMixin(LoginRequiredMixin):
    """PONTO ÚNICO DE INTEGRAÇÃO com login e permissões.

    Hoje exige apenas usuário autenticado (autenticação padrão do Django).
    Quando o módulo de permissões existir, trocar a herança por
    PermissionRequiredMixin (ou o mecanismo escolhido pela equipe) AQUI,
    sem mexer nas demais views.
    """
