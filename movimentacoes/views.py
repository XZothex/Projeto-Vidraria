from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from . import services
from .forms import AjusteForm, EntradaForm, FiltroHistoricoForm, PerdaForm
from .mixins import AcessoMovimentacoesMixin
from .services import EstoqueError


class HistoricoView(AcessoMovimentacoesMixin, TemplateView):
    """Histórico de movimentações, com filtros básicos."""

    template_name = "movimentacoes/historico.html"
    limite = 200

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        filtro = FiltroHistoricoForm(self.request.GET or None, conn=self.conn)
        dados = filtro.cleaned_data if filtro.is_valid() else {}
        tipo = dados.get("tipo")
        movimentacoes = services.listar_movimentacoes(
            self.conn,
            tipos=(tipo,) if tipo else services.TIPOS_HISTORICO,
            id_material=int(dados["id_material"]) if dados.get("id_material") else None,
            data_inicio=dados.get("data_inicio"),
            data_fim=dados.get("data_fim"),
            limite=self.limite,
        )
        for movimento in movimentacoes:
            movimento["rotulo"] = services.TIPOS_HISTORICO[movimento["tipo"]]
        contexto.update(filtro=filtro, movimentacoes=movimentacoes, limite=self.limite, aba="historico")
        return contexto


class LotesView(AcessoMovimentacoesMixin, TemplateView):
    """Saldo físico, reservado e disponível de cada lote."""

    template_name = "movimentacoes/lotes.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        lotes = services.listar_lotes(self.conn)
        busca = self.request.GET.get("q", "").strip().lower()
        if busca:
            lotes = [l for l in lotes if busca in f"{l['codigo']} {l['descricao']} {l['localizacao']}".lower()]
        contexto.update(lotes=lotes, busca=busca, aba="lotes")
        return contexto


class OperacaoView(AcessoMovimentacoesMixin, FormView):
    """Base das três telas: abre o formulário, chama o serviço e trata erros de regra."""

    template_name = "movimentacoes/operacao_form.html"
    success_url = reverse_lazy("movimentacoes:historico")
    titulo = ""
    botao = "Registrar"
    classe_botao = "btn-primary"
    perfis = set()
    acao = ""  # "registrar entradas", usado na mensagem de acesso negado

    def negar_acesso(self):
        if self.usuario["perfil"] not in self.perfis:
            return render(self.request, "movimentacoes/sem_permissao.html", {"acao": self.acao}, status=403)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["conn"] = self.conn
        return kwargs

    def get_initial(self):
        lote = self.request.GET.get("lote", "")
        return {"id_estoque": lote} if lote.isdigit() else {}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(titulo=self.titulo, botao=self.botao, classe_botao=self.classe_botao)
        return contexto

    def form_valid(self, form):
        try:
            mensagem = self.executar(form.cleaned_data)
        except EstoqueError as erro:
            form.add_error(None, str(erro))
            return self.form_invalid(form)
        messages.success(self.request, mensagem)
        return redirect(self.get_success_url())

    def executar(self, dados):
        raise NotImplementedError


def _id(valor):
    return int(valor) if valor else None


class EntradaView(OperacaoView):
    form_class = EntradaForm
    titulo = "Registrar entrada (recebimento)"
    botao = "Registrar entrada"
    perfis = services.PERFIS_ENTRADA
    acao = "registrar entradas"

    def executar(self, d):
        r = services.registrar_entrada(
            self.conn, id_usuario=self.usuario["id_usuario"], quantidade=d["quantidade"],
            nota_fiscal=d["nota_fiscal"], id_estoque=_id(d["id_estoque"]), id_material=_id(d["id_material"]),
            localizacao=d["localizacao"], id_fornecedor=_id(d["id_fornecedor"]),
            largura_mm=d["largura_mm"], altura_mm=d["altura_mm"],
            custo_unitario=d["custo_unitario"] or None, motivo=d["motivo"],
        )
        origem = "em um lote novo" if r["lote_novo"] else "no lote existente"
        return f"Entrada registrada {origem} (#{r['id_estoque']}). Saldo físico: {services.formatar_quantidade(r['saldo_fisico'])}."


class PerdaView(OperacaoView):
    form_class = PerdaForm
    titulo = "Registrar perda (quebra, defeito ou extravio)"
    botao = "Registrar perda"
    classe_botao = "btn-danger"
    perfis = services.PERFIS_PERDA
    acao = "registrar perdas"

    def executar(self, d):
        r = services.registrar_perda(
            self.conn, id_estoque=int(d["id_estoque"]), quantidade=d["quantidade"],
            categoria=d["categoria"], motivo=d["motivo"], id_usuario=self.usuario["id_usuario"],
        )
        return f"Perda registrada no lote #{r['id_estoque']}. Saldo físico: {services.formatar_quantidade(r['saldo_fisico'])}."


class AjusteView(OperacaoView):
    form_class = AjusteForm
    titulo = "Ajuste de inventário (contagem física)"
    botao = "Registrar ajuste"
    classe_botao = "btn-warning"
    perfis = services.PERFIS_AJUSTE
    acao = "autorizar ajustes de estoque"

    def executar(self, d):
        r = services.registrar_ajuste(
            self.conn, id_estoque=int(d["id_estoque"]), quantidade_contada=d["quantidade_contada"],
            justificativa=d["justificativa"], id_usuario=self.usuario["id_usuario"],
        )
        sinal = "+" if r["diferenca"] > 0 else ""
        return (f"Ajuste registrado no lote #{r['id_estoque']}: {sinal}{services.formatar_quantidade(r['diferenca'])}. "
                f"Saldo físico: {services.formatar_quantidade(r['saldo_fisico'])}.")
