from django.contrib.auth.mixins import LoginRequiredMixin


class AcessoPedidosMixin(LoginRequiredMixin):
    """PONTO ÚNICO DE INTEGRAÇÃO com login e permissões do módulo de pedidos.

    Hoje exige apenas usuário autenticado. Quando o módulo de permissões existir,
    trocar a herança AQUI (ex.: PermissionRequiredMixin), sem mexer nas views.
    """
