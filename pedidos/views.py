import re

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from cadastros.views import ListaFiltradaMixin

from . import estoque, services
from .forms import CancelamentoForm, ClienteForm, EntregaForm, ItemPedidoForm, PedidoForm
from .mixins import AcessoPedidosMixin
from .models import Cliente, ItemPedido, Pedido, Reserva
from .services import RegraDeNegocioError


# ------------------------------- Clientes ----------------------------------
class ClienteListView(AcessoPedidosMixin, ListaFiltradaMixin, ListView):
    model = Cliente
    template_name = "pedidos/cliente/lista.html"
    context_object_name = "clientes"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            filtro = Q(nome__icontains=q)
            if re.fullmatch(r"[\d.\-/\s]+", q):
                digitos = re.sub(r"\D", "", q)
                if digitos:
                    filtro |= Q(cpf_cnpj__contains=digitos)
            qs = qs.filter(filtro)
        return self.filtrar_situacao(qs)


class ClienteDetailView(AcessoPedidosMixin, DetailView):
    model = Cliente
    template_name = "pedidos/cliente/detalhe.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["pedidos_recentes"] = self.object.pedidos.all()[:10]
        return contexto


class ClienteCreateView(AcessoPedidosMixin, SuccessMessageMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "pedidos/cliente/form.html"
    success_message = "Cliente cadastrado com sucesso."


class ClienteUpdateView(AcessoPedidosMixin, SuccessMessageMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "pedidos/cliente/form.html"
    success_message = "Cliente atualizado com sucesso."


class ClienteSituacaoView(AcessoPedidosMixin, View):
    """Inativar/reativar (somente POST). Clientes nunca são apagados."""

    http_method_names = ["post"]
    ativar = False

    def post(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        cliente.ativo = self.ativar
        cliente.save(update_fields=["ativo", "atualizado_em"])
        verbo = "reativado" if self.ativar else "inativado"
        messages.success(request, f'Cliente "{cliente}" {verbo}.')
        return redirect(cliente)


# -------------------------------- Pedidos ----------------------------------
class PedidoListView(AcessoPedidosMixin, ListaFiltradaMixin, ListView):
    model = Pedido
    template_name = "pedidos/pedido/lista.html"
    context_object_name = "pedidos"

    def get_queryset(self):
        qs = super().get_queryset().select_related("cliente").annotate(qtd_itens=Count("itens"))
        qs = qs.order_by("-criado_em", "-pk")  # o annotate descarta a ordenação padrão
        q = self.request.GET.get("q", "").strip()
        if q:
            filtro = Q(cliente__nome__icontains=q)
            numero = q.lstrip("#")
            if numero.isdigit() and len(numero) <= 9:
                filtro |= Q(pk=int(numero))
            qs = qs.filter(filtro)
        status = self.request.GET.get("status", "")
        if status in Pedido.Status.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["status_opcoes"] = Pedido.Status.choices
        contexto["status"] = self.request.GET.get("status", "")
        return contexto


class PedidoDetailView(AcessoPedidosMixin, DetailView):
    template_name = "pedidos/pedido/detalhe.html"
    context_object_name = "pedido"

    def get_queryset(self):
        return Pedido.objects.select_related("cliente", "cancelado_por").prefetch_related(
            Prefetch("itens", queryset=ItemPedido.objects.select_related("material")),
            "itens__reservas",
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        pedido = self.object
        itens = list(pedido.itens.all())
        reservados = sum(1 for i in itens if i.reservado)
        contexto.update(
            itens=itens,
            qtd_reservados=reservados,
            qtd_pendentes=len(itens) - reservados,
            pode_entregar=bool(itens) and reservados == len(itens),
            entrega=getattr(pedido, "entrega", None) if pedido.status == Pedido.Status.ENTREGUE else None,
        )
        # Disponibilidade só aparece quando o módulo de estoque informar o saldo.
        for item in itens:
            item.disponivel = estoque.quantidade_disponivel(item.material) if pedido.aberto else None
        return contexto


class PedidoCreateView(AcessoPedidosMixin, SuccessMessageMixin, CreateView):
    model = Pedido
    form_class = PedidoForm
    template_name = "pedidos/pedido/form.html"
    success_message = "Pedido criado. Agora adicione os itens."

    def get_initial(self):
        inicial = super().get_initial()
        cliente = self.request.GET.get("cliente", "")
        if cliente.isdigit() and len(cliente) <= 9:
            inicial["cliente"] = int(cliente)
        return inicial

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        return super().form_valid(form)


class PedidoAbertoMixin:
    """Só deixa passar quando o pedido (URL) está aberto; senão volta ao detalhe com aviso."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            pedido = get_object_or_404(Pedido, pk=kwargs.get("pedido_pk", kwargs.get("pk")))
            if not pedido.aberto:
                messages.error(
                    request, f"O {pedido} está {pedido.get_status_display().lower()} e não pode mais ser alterado."
                )
                return redirect(pedido)
        return super().dispatch(request, *args, **kwargs)


class PedidoUpdateView(AcessoPedidosMixin, PedidoAbertoMixin, SuccessMessageMixin, UpdateView):
    model = Pedido
    form_class = PedidoForm
    template_name = "pedidos/pedido/form.html"
    success_message = "Pedido atualizado com sucesso."


# ---------------------------- Itens do pedido -------------------------------
class ItemFormMixin(AcessoPedidosMixin, PedidoAbertoMixin):
    form_class = ItemPedidoForm
    template_name = "pedidos/pedido/item_form.html"

    def get_pedido(self):
        return get_object_or_404(Pedido, pk=self.kwargs["pedido_pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["pedido"] = self.get_pedido()
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["pedido"] = self.get_pedido()
        return contexto

    def get_success_url(self):
        return self.get_pedido().get_absolute_url()

    def form_valid(self, form):
        try:
            self.object = services.salvar_item(form.save(commit=False))
        except RegraDeNegocioError as erro:
            form.add_error(None, str(erro))
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())


class ItemCreateView(ItemFormMixin, CreateView):
    model = ItemPedido
    success_message = "Item adicionado."


class ItemUpdateView(ItemFormMixin, UpdateView):
    success_message = "Item atualizado."

    def get_queryset(self):
        return ItemPedido.objects.filter(pedido_id=self.kwargs["pedido_pk"])


# ------------------- Ações (somente POST): reservar, liberar... -------------
class AcaoPedidoView(AcessoPedidosMixin, View):
    """Executa uma regra de negócio e volta ao detalhe do pedido com a mensagem."""

    http_method_names = ["post"]

    def executar(self, request, pedido):  # pragma: no cover - sobrescrito
        raise NotImplementedError

    def post(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        try:
            mensagem = self.executar(request, pedido)
        except RegraDeNegocioError as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, mensagem)
        return redirect(pedido)


class PedidoReservarView(AcaoPedidoView):
    def executar(self, request, pedido):
        qtd = services.reservar(pedido, request.user)
        return f"{qtd} item(ns) reservado(s)."


class PedidoLiberarView(AcaoPedidoView):
    def executar(self, request, pedido):
        qtd = services.liberar(pedido, request.user)
        return f"{qtd} reserva(s) liberada(s)."


class AcaoItemView(AcaoPedidoView):
    def post(self, request, pk, item_pk):
        self.item = get_object_or_404(ItemPedido, pk=item_pk, pedido_id=pk)
        return super().post(request, pk)


class ItemReservarView(AcaoItemView):
    def executar(self, request, pedido):
        services.reservar(pedido, request.user, itens=[self.item])
        return "Item reservado."


class ItemLiberarView(AcaoItemView):
    def executar(self, request, pedido):
        services.liberar(pedido, request.user, itens=[self.item])
        return "Reserva liberada."


class ItemRemoverView(AcaoItemView):
    def executar(self, request, pedido):
        services.remover_item(self.item)
        return "Item removido."


# ----------------------- Cancelamento e entrega (com formulário) ------------
class AcaoComFormularioView(AcessoPedidosMixin, PedidoAbertoMixin, FormView):
    template_name = "pedidos/pedido/acao_form.html"
    titulo = ""
    botao = ""
    classe_botao = "btn-primary"

    def get_pedido(self):
        return get_object_or_404(Pedido, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(pedido=self.get_pedido(), titulo=self.titulo, botao=self.botao, classe_botao=self.classe_botao)
        return contexto

    def get_success_url(self):
        return self.get_pedido().get_absolute_url()

    def form_valid(self, form):
        try:
            mensagem = self.executar(form)
        except RegraDeNegocioError as erro:
            form.add_error(None, str(erro))
            return self.form_invalid(form)
        messages.success(self.request, mensagem)
        return redirect(self.get_success_url())


class PedidoCancelarView(AcaoComFormularioView):
    form_class = CancelamentoForm
    titulo = "Cancelar pedido"
    botao = "Confirmar cancelamento"
    classe_botao = "btn-danger"

    def executar(self, form):
        services.cancelar(self.get_pedido(), self.request.user, form.cleaned_data["motivo"])
        return "Pedido cancelado e reservas liberadas."


class PedidoEntregarView(AcaoComFormularioView):
    form_class = EntregaForm
    titulo = "Registrar entrega"
    botao = "Registrar entrega"
    classe_botao = "btn-success"

    def executar(self, form):
        dados = form.cleaned_data
        services.registrar_entrega(
            self.get_pedido(), self.request.user,
            dados["data_entrega"], dados["recebido_por"], dados["observacoes"],
        )
        return "Entrega registrada. As reservas foram baixadas."
