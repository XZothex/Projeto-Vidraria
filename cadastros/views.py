import re

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from django.contrib.messages.views import SuccessMessageMixin

from .forms import FornecedorForm, MaterialForm
from .mixins import AcessoCadastrosMixin
from .models import Fornecedor, Material

POR_PAGINA = 10


class ListaFiltradaMixin:
    """Paginação + filtro de situação (ativo/inativo) + querystring para os links de página."""

    paginate_by = POR_PAGINA

    def filtrar_situacao(self, qs):
        situacao = self.request.GET.get("situacao", "")
        if situacao == "ativo":
            return qs.filter(ativo=True)
        if situacao == "inativo":
            return qs.filter(ativo=False)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        contexto["querystring"] = params.urlencode()
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["situacao"] = self.request.GET.get("situacao", "")
        return contexto


# ----------------------------- Materiais -----------------------------------
class MaterialListView(AcessoCadastrosMixin, ListaFiltradaMixin, ListView):
    model = Material
    template_name = "cadastros/material/lista.html"
    context_object_name = "materiais"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(codigo__icontains=q))
        categoria = self.request.GET.get("categoria", "")
        if categoria in Material.Categoria.values:
            qs = qs.filter(categoria=categoria)
        return self.filtrar_situacao(qs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["categorias"] = Material.Categoria.choices
        contexto["categoria"] = self.request.GET.get("categoria", "")
        return contexto


class MaterialDetailView(AcessoCadastrosMixin, DetailView):
    model = Material
    template_name = "cadastros/material/detalhe.html"


class MaterialCreateView(AcessoCadastrosMixin, SuccessMessageMixin, CreateView):
    model = Material
    form_class = MaterialForm
    template_name = "cadastros/material/form.html"
    success_message = "Material cadastrado com sucesso."


class MaterialUpdateView(AcessoCadastrosMixin, SuccessMessageMixin, UpdateView):
    model = Material
    form_class = MaterialForm
    template_name = "cadastros/material/form.html"
    success_message = "Material atualizado com sucesso."


# ---------------------------- Fornecedores ---------------------------------
class FornecedorListView(AcessoCadastrosMixin, ListaFiltradaMixin, ListView):
    model = Fornecedor
    template_name = "cadastros/fornecedor/lista.html"
    context_object_name = "fornecedores"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            filtro = Q(nome__icontains=q) | Q(nome_fantasia__icontains=q)
            # Se o termo parece um documento (só dígitos e pontuação), busca também no CPF/CNPJ.
            if re.fullmatch(r"[\d.\-/\s]+", q):
                digitos = re.sub(r"\D", "", q)
                if digitos:
                    filtro |= Q(cpf_cnpj__contains=digitos)
            qs = qs.filter(filtro)
        return self.filtrar_situacao(qs)


class FornecedorDetailView(AcessoCadastrosMixin, DetailView):
    model = Fornecedor
    template_name = "cadastros/fornecedor/detalhe.html"


class FornecedorCreateView(AcessoCadastrosMixin, SuccessMessageMixin, CreateView):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = "cadastros/fornecedor/form.html"
    success_message = "Fornecedor cadastrado com sucesso."


class FornecedorUpdateView(AcessoCadastrosMixin, SuccessMessageMixin, UpdateView):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = "cadastros/fornecedor/form.html"
    success_message = "Fornecedor atualizado com sucesso."


# ------------------- Inativar / reativar (somente POST) --------------------
class AlterarSituacaoView(AcessoCadastrosMixin, View):
    """Ação que altera dados: aceita apenas POST (GET devolve 405)."""

    http_method_names = ["post"]
    model = None
    ativar = False
    mensagem = ""

    def post(self, request, pk):
        objeto = get_object_or_404(self.model, pk=pk)
        objeto.ativo = self.ativar
        objeto.save(update_fields=["ativo", "atualizado_em"])
        messages.success(request, self.mensagem.format(objeto=objeto))
        return redirect(objeto.get_absolute_url())


class MaterialInativarView(AlterarSituacaoView):
    model, ativar, mensagem = Material, False, 'Material "{objeto}" inativado.'


class MaterialReativarView(AlterarSituacaoView):
    model, ativar, mensagem = Material, True, 'Material "{objeto}" reativado.'


class FornecedorInativarView(AlterarSituacaoView):
    model, ativar, mensagem = Fornecedor, False, 'Fornecedor "{objeto}" inativado.'


class FornecedorReativarView(AlterarSituacaoView):
    model, ativar, mensagem = Fornecedor, True, 'Fornecedor "{objeto}" reativado.'
