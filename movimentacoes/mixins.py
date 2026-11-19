from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from pymysql.err import OperationalError

from . import services


class AcessoMovimentacoesMixin(LoginRequiredMixin):
    """PONTO ÚNICO DE INTEGRAÇÃO com login/permissões e com o banco MySQL.

    * Exige usuário autenticado (autenticação padrão do Django).
    * O banco MySQL tem sua própria tabela ``usuario`` (com o ``perfil``). O usuário do
      Django é ligado a ela pelo LOGIN: ``username`` do Django == ``usuario.login``.
      Quando o módulo de login/permissões definir outra forma de ligar os dois, é só
      trocar ``buscar_usuario`` aqui.
    * Abre a conexão MySQL no início da requisição (``self.conn``) e a fecha no fim.
    * Views que restringem por perfil sobrescrevem ``negar_acesso``.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        try:
            self.conn = services.conectar()
        except OperationalError:
            return render(request, "movimentacoes/banco_indisponivel.html", status=503)
        try:
            self.usuario = self.buscar_usuario(request)
            if self.usuario is None:
                return render(request, "movimentacoes/sem_usuario.html", status=403)
            resposta = self.negar_acesso()
            if resposta is not None:
                return resposta
            return super().dispatch(request, *args, **kwargs)
        finally:
            self.conn.close()

    def buscar_usuario(self, request):
        return services.buscar_usuario_por_login(self.conn, request.user.get_username())

    def negar_acesso(self):
        """Devolve uma resposta de erro para barrar o acesso, ou ``None`` para liberar."""
        return None

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        perfil = self.usuario["perfil"]
        contexto.update(
            usuario_estoque=self.usuario,
            pode_entrada=perfil in services.PERFIS_ENTRADA,
            pode_perda=perfil in services.PERFIS_PERDA,
            pode_ajuste=perfil in services.PERFIS_AJUSTE,
        )
        return contexto
