import csv
from datetime import date, datetime, time

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Sum, Q
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView

from cadastros.models import Material
from pedidos.models import Cliente, Entrega, Pedido, Reserva


def _data(valor):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def _historico(request):
    """Reúne eventos de pedidos que o Django registra."""
    eventos = []
    reservas = Reserva.objects.select_related(
        "item__pedido__cliente", "item__material", "criada_por", "encerrada_por"
    )
    for r in reservas:
        eventos.append({
            "data": r.criada_em, "tipo": "Reserva criada", "material": r.item.material.nome,
            "quantidade": r.quantidade, "pedido": r.item.pedido.numero,
            "cliente": r.item.pedido.cliente.nome, "usuario": r.criada_por.get_username() if r.criada_por else "—",
            "detalhe": "Item reservado",
        })
        if r.encerrada_em and r.status != Reserva.Status.ATIVA:
            tipo = "Reserva consumida na entrega" if r.status == Reserva.Status.CONSUMIDA else "Reserva liberada"
            usuario = r.encerrada_por.get_username() if r.encerrada_por else "—"
            eventos.append({
                "data": r.encerrada_em, "tipo": tipo, "material": r.item.material.nome,
                "quantidade": r.quantidade, "pedido": r.item.pedido.numero,
                "cliente": r.item.pedido.cliente.nome, "usuario": usuario,
                "detalhe": r.get_status_display(),
            })
    entregas = Entrega.objects.select_related("pedido__cliente", "registrado_por").prefetch_related("pedido__itens__material")
    for e in entregas:
        itens = list(e.pedido.itens.all())
        if itens:
            for item in itens:
                eventos.append({
                    "data": timezone.make_aware(datetime.combine(e.data_entrega, time.min)),
                    "tipo": "Entrega registrada", "material": item.material.nome,
                    "quantidade": item.quantidade, "pedido": e.pedido.numero,
                    "cliente": e.pedido.cliente.nome,
                    "usuario": e.registrado_por.get_username() if e.registrado_por else "—",
                    "detalhe": e.recebido_por,
                })
    cancelados = Pedido.objects.filter(status=Pedido.Status.CANCELADO).select_related("cliente", "cancelado_por")
    for p in cancelados:
        if p.cancelado_em:
            eventos.append({
                "data": p.cancelado_em, "tipo": "Pedido cancelado", "material": "—",
                "quantidade": "—", "pedido": p.numero, "cliente": p.cliente.nome,
                "usuario": p.cancelado_por.get_username() if p.cancelado_por else "—",
                "detalhe": p.motivo_cancelamento or "—",
            })
    eventos.sort(key=lambda e: e["data"], reverse=True)

    q = request.GET.get("q", "").strip().lower()
    tipo = request.GET.get("tipo", "").strip().lower()
    inicio, fim = _data(request.GET.get("inicio")), _data(request.GET.get("fim"))
    if q:
        eventos = [e for e in eventos if q in " ".join(str(e[k]) for k in ("tipo","material","pedido","cliente","usuario","detalhe")).lower()]
    if tipo:
        eventos = [e for e in eventos if tipo in e["tipo"].lower()]
    if inicio:
        eventos = [e for e in eventos if timezone.localtime(e["data"]).date() >= inicio]
    if fim:
        eventos = [e for e in eventos if timezone.localtime(e["data"]).date() <= fim]
    return eventos


COLUNAS_EVENTOS = ["Data", "Tipo", "Material", "Quantidade", "Pedido", "Cliente", "Usuário", "Detalhe"]


def _linha_evento(evento):
    return [evento[chave] for chave in ("data", "tipo", "material", "quantidade", "pedido", "cliente", "usuario", "detalhe")]


def _csv(nome, colunas, linhas):
    resposta = HttpResponse("\ufeff", content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}.csv"'
    writer = csv.writer(resposta, delimiter=";")
    writer.writerow(colunas)
    for linha in linhas:
        valores = []
        for valor in linha:
            if isinstance(valor, datetime):
                valor = timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")
            if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@")):
                valor = "'" + valor
            valores.append(valor)
        writer.writerow(valores)
    return resposta


def _parametros(request):
    parametros = request.GET.copy()
    parametros.pop("page", None)
    parametros.pop("exportar", None)
    base = parametros.urlencode()
    parametros["exportar"] = "csv"
    return {"pagina_query": base, "csv_query": parametros.urlencode()}


def _acesso_estoque(usuario):
    if connection.vendor != "mysql":
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM usuario WHERE login = %s", [usuario.get_username()])
        return cursor.fetchone() is not None


def _estoque_por_origem(q=""):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT codigo, descricao, unidade, origem, SUM(fisico), SUM(reservado), SUM(disponivel) "
            "FROM saldo_estoque WHERE (LOCATE(LOWER(%s), LOWER(codigo)) > 0 OR LOCATE(LOWER(%s), LOWER(descricao)) > 0) "
            "GROUP BY codigo, descricao, unidade, origem ORDER BY codigo, origem",
            [q, q],
        )
        return cursor.fetchall()


def _reservas(q, estoque_mysql):
    reservas = Reserva.objects.filter(status=Reserva.Status.ATIVA).select_related(
        "item__material", "item__pedido__cliente",
    )
    if q:
        reservas = reservas.filter(
            Q(item__material__nome__icontains=q) | Q(item__material__codigo__icontains=q)
            | Q(item__pedido__cliente__nome__icontains=q)
        )
    if estoque_mysql:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_reserva, quantidade FROM reserva WHERE status IN ('ativa', 'separada')")
            pendentes = dict(cursor.fetchall())
        return [(reserva, qtd) for reserva in reservas
                if (qtd := sum(pendentes.get(pk, 0) for pk in reserva.mysql_reservas))]
    return [(reserva, reserva.quantidade) for reserva in reservas]


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "painel/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        estoque_mysql = _acesso_estoque(self.request.user)
        reservas = _reservas("", estoque_mysql) if estoque_mysql or connection.vendor != "mysql" else None
        materiais_reservados = {}
        for reserva, quantidade in reservas or ():
            material = reserva.item.material
            chave = (material.codigo, material.nome, material.get_unidade_controle_display())
            materiais_reservados[chave] = materiais_reservados.get(chave, 0) + quantidade
        ctx.update({
            "total_materiais": Material.objects.filter(ativo=True).count(),
            "total_pedidos_abertos": Pedido.objects.filter(status=Pedido.Status.ABERTO).count(),
            "total_pedidos_entregues": Pedido.objects.filter(status=Pedido.Status.ENTREGUE).count(),
            "total_reservas": len(reservas) if reservas is not None else None,
            "estoque_mysql": estoque_mysql,
            "pedidos_recentes": Pedido.objects.select_related("cliente").order_by("-criado_em")[:6],
            "materiais_reservados": sorted(materiais_reservados.items(), key=lambda par: par[0]),
            "eventos_recentes": _historico(self.request)[:8],
        })
        return ctx


class HistoricoView(LoginRequiredMixin, TemplateView):
    template_name = "painel/historico.html"

    def get(self, request, *args, **kwargs):
        if request.GET.get("exportar") == "csv":
            return _csv("historico_pedidos", COLUNAS_EVENTOS, map(_linha_evento, _historico(request)))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        eventos = _historico(self.request)
        pagina = Paginator(eventos, 20).get_page(self.request.GET.get("page"))
        ctx.update(_parametros(self.request), pagina=pagina, eventos=pagina.object_list, total_eventos=len(eventos))
        return ctx


RELATORIOS = {
    "posicao": "Posição de estoque",
    "reservas": "Reservas pendentes",
    "pedidos": "Situação dos pedidos",
    "movimentacoes": "Eventos de pedidos",
}


class RelatoriosView(LoginRequiredMixin, TemplateView):
    template_name = "painel/relatorios.html"
    extra_context = {"relatorios": RELATORIOS}


def _relatorio(request, tipo):
    q = request.GET.get("q", "").strip()
    if tipo == "posicao":
        if _acesso_estoque(request.user):
            return ["Código", "Material", "Unidade", "Origem", "Físico", "Reservado", "Disponível"], _estoque_por_origem(q)
        if connection.vendor == "mysql":
            raise PermissionDenied("O usuário ainda não está vinculado ao estoque MySQL.")
        materiais = Material.objects.filter(ativo=True).filter(Q(nome__icontains=q) | Q(codigo__icontains=q))
        materiais = materiais.annotate(reservado=Sum("itens_pedido__reservas__quantidade",
            filter=Q(itens_pedido__reservas__status=Reserva.Status.ATIVA))).order_by("nome")
        return ["Código", "Material", "Unidade", "Reservado"], [
            (m.codigo, m.nome, m.get_unidade_controle_display(), m.reservado or 0) for m in materiais
        ]
    if tipo == "reservas":
        estoque_mysql = _acesso_estoque(request.user)
        if connection.vendor == "mysql" and not estoque_mysql:
            raise PermissionDenied("O usuário ainda não está vinculado ao estoque MySQL.")
        return ["Data", "Material", "Quantidade", "Unidade", "Pedido", "Cliente"], [
            (r.criada_em, r.item.material.nome, qtd, r.item.material.get_unidade_controle_display(),
             r.item.pedido.numero, r.item.pedido.cliente.nome) for r, qtd in _reservas(q, estoque_mysql)
        ]
    if tipo == "pedidos":
        pedidos = Pedido.objects.select_related("cliente").annotate(qtd_itens=Count("itens")).order_by("-criado_em")
        if q:
            pedidos = pedidos.filter(cliente__nome__icontains=q)
        return ["Pedido", "Cliente", "Itens", "Situação", "Criação"], [
            (p.numero, p.cliente.nome, p.qtd_itens, p.get_status_display(), p.criado_em) for p in pedidos
        ]
    return COLUNAS_EVENTOS, list(map(_linha_evento, _historico(request)))


class RelatorioView(LoginRequiredMixin, TemplateView):
    template_name = "painel/relatorio.html"

    def get(self, request, *args, **kwargs):
        tipo = kwargs["tipo"]
        if tipo not in RELATORIOS:
            raise Http404("Relatório não encontrado.")
        colunas, linhas = _relatorio(request, tipo)
        if request.GET.get("exportar") == "csv":
            return _csv(f"relatorio_{tipo}", colunas, linhas)
        return self.render_to_response(self.get_context_data(
            titulo=RELATORIOS[tipo], tipo=tipo, colunas=colunas, linhas=linhas,
            saldo_local=tipo == "posicao" and connection.vendor != "mysql", **_parametros(request),
        ))
