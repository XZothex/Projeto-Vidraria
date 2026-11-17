import re

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from cadastros.views import ListaFiltradaMixin

from .forms import ClienteForm
from .mixins import AcessoPedidosMixin
from .models import Cliente


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
