from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, connection
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import DetailView, ListView, CreateView
from .forms import ChapaDisponivelForm, OperacaoCorteForm, PecaFormSet, SobraFormSet
from .models import ChapaDisponivel, OperacaoCorte
from .services import registrar_operacao


class CortesHomeView(LoginRequiredMixin, ListView):
    model = OperacaoCorte
    template_name = "cortes/lista.html"
    context_object_name = "operacoes"
    paginate_by = 15

    def get_context_data(self, **kwargs):
        return super().get_context_data(estoque_local=connection.vendor != "mysql", **kwargs)

    def get_queryset(self):
        qs = OperacaoCorte.objects.select_related("pedido", "pedido__cliente", "material", "realizado_por")
        termo = self.request.GET.get("q", "").strip()
        if termo:
            qs = qs.filter(Q(pedido__cliente__nome__icontains=termo) | Q(material__nome__icontains=termo) | Q(observacoes__icontains=termo))
        return qs


class EstoqueLocalMixin:
    def dispatch(self, request, *args, **kwargs):
        if connection.vendor == "mysql":
            return redirect("movimentacoes:lotes")
        return super().dispatch(request, *args, **kwargs)


class ChapaListView(LoginRequiredMixin, EstoqueLocalMixin, ListView):
    model = ChapaDisponivel
    template_name = "cortes/chapas.html"
    context_object_name = "chapas"
    paginate_by = 20

    def get_queryset(self):
        return ChapaDisponivel.objects.select_related("material").filter(status=ChapaDisponivel.Status.DISPONIVEL)


class ChapaCreateView(LoginRequiredMixin, EstoqueLocalMixin, CreateView):
    form_class = ChapaDisponivelForm
    template_name = "cortes/chapa_form.html"
    success_url = "/cortes/chapas/"

    def form_valid(self, form):
        messages.success(self.request, "Chapa/sobra cadastrada para utilização nos cortes.")
        return super().form_valid(form)


class OperacaoCreateView(LoginRequiredMixin, View):
    template_name = "cortes/operacao_form.html"

    def get(self, request):
        return self.render_forms(request, OperacaoCorteForm(), PecaFormSet(prefix="pecas"), SobraFormSet(prefix="sobras"))

    def post(self, request):
        form = OperacaoCorteForm(request.POST)
        pecas = PecaFormSet(request.POST, prefix="pecas")
        sobras = SobraFormSet(request.POST, prefix="sobras")
        if form.is_valid() and pecas.is_valid() and sobras.is_valid():
            operacao = form.save(commit=False)
            dados_pecas = [f.cleaned_data for f in pecas.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
            dados_sobras = [f.cleaned_data for f in sobras.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
            for d in dados_pecas:
                d.pop("DELETE", None)
                d.pop("id", None)
                d.pop("operacao", None)
            for d in dados_sobras:
                d.pop("DELETE", None)
                d.pop("id", None)
                d.pop("operacao", None)
            try:
                registrar_operacao(
                    operacao=operacao, pecas=dados_pecas, sobras=dados_sobras, usuario=request.user,
                    id_reserva_mysql=form.cleaned_data.get("id_reserva_mysql"),
                )
            except ValidationError as exc:
                for mensagem in exc.messages:
                    form.add_error(None, mensagem)
            except IntegrityError:
                form.add_error(None, "O banco recusou a baixa. Confira a reserva e o saldo do lote.")
            except OperationalError as exc:
                if not exc.args or exc.args[0] not in (1205, 1213):
                    raise
                form.add_error(None, "O estoque está ocupado. Tente registrar o corte novamente.")
            else:
                messages.success(request, "Corte registrado e sobras disponibilizadas no estoque.")
                return redirect("cortes:detalhe", pk=operacao.pk)
        return self.render_forms(request, form, pecas, sobras)

    def render_forms(self, request, form, pecas, sobras):
        return render(request, self.template_name, {"form": form, "pecas": pecas, "sobras": sobras, "usa_mysql": connection.vendor == "mysql"})


class OperacaoDetailView(LoginRequiredMixin, DetailView):
    model = OperacaoCorte
    template_name = "cortes/detalhe.html"
    context_object_name = "operacao"

    def get_queryset(self):
        return OperacaoCorte.objects.select_related("pedido", "pedido__cliente", "item_pedido", "material", "realizado_por", "chapa_estoque").prefetch_related("pecas", "sobras__chapa_gerada")
