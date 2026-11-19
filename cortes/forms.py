from django import forms
from django.db import connection
from django.forms import inlineformset_factory
from cadastros.models import Material
from pedidos.models import ItemPedido, Pedido
from .models import ChapaDisponivel, OperacaoCorte, PecaCortada, Sobra


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "form-control")


class ChapaDisponivelForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ChapaDisponivel
        fields = ["material", "tipo", "largura_mm", "altura_mm", "espessura_mm", "codigo", "origem_descricao"]
        widgets = {
            "largura_mm": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "altura_mm": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "espessura_mm": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(ativo=True, categoria=Material.Categoria.VIDRO)


class OperacaoCorteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = OperacaoCorte
        fields = ["pedido", "item_pedido", "material", "origem", "chapa_estoque", "largura_chapa_mm", "altura_chapa_mm", "espessura_mm", "quantidade_chapas", "kerf_mm", "observacoes"]
        widgets = {
            "largura_chapa_mm": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "altura_chapa_mm": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "espessura_mm": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "quantidade_chapas": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "kerf_mm": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pedido"].queryset = Pedido.objects.filter(status=Pedido.Status.ABERTO).order_by("-criado_em")
        self.fields["item_pedido"].queryset = ItemPedido.objects.select_related("pedido", "material").filter(pedido__status=Pedido.Status.ABERTO)
        self.fields["material"].queryset = Material.objects.filter(ativo=True, categoria=Material.Categoria.VIDRO)
        self.fields["chapa_estoque"].queryset = ChapaDisponivel.objects.filter(status=ChapaDisponivel.Status.DISPONIVEL, material__categoria=Material.Categoria.VIDRO).select_related("material")
        self.fields["chapa_estoque"].required = False
        self.fields["largura_chapa_mm"].required = False
        self.fields["altura_chapa_mm"].required = False
        if connection.vendor == "mysql":
            self.fields["origem"].choices = [(OperacaoCorte.Origem.MYSQL, "Lote reservado no MySQL")]
            self.fields["origem"].initial = OperacaoCorte.Origem.MYSQL
            for campo in ("chapa_estoque", "largura_chapa_mm", "altura_chapa_mm", "espessura_mm", "quantidade_chapas"):
                del self.fields[campo]
        else:
            self.fields["origem"].choices = [("", "---------"), *[
                item for item in OperacaoCorte.Origem.choices if item[0] != OperacaoCorte.Origem.MYSQL
            ]]


    def clean(self):
        dados = super().clean()
        pedido, item, material = dados.get("pedido"), dados.get("item_pedido"), dados.get("material")
        origem, chapa = dados.get("origem"), dados.get("chapa_estoque")
        if pedido and item and item.pedido_id != pedido.pk:
            self.add_error("item_pedido", "Selecione um item pertencente ao pedido.")
        if item and material and item.material_id != material.pk:
            self.add_error("material", "O material deve corresponder ao item do pedido.")
        if origem == OperacaoCorte.Origem.MANUAL:
            if not dados.get("largura_chapa_mm"):
                self.add_error("largura_chapa_mm", "Informe a largura da chapa em milímetros.")
            if not dados.get("altura_chapa_mm"):
                self.add_error("altura_chapa_mm", "Informe a altura da chapa em milímetros.")
        if origem == OperacaoCorte.Origem.ESTOQUE:
            if dados.get("quantidade_chapas") not in (None, 1):
                self.add_error("quantidade_chapas", "Uma unidade cadastrada no estoque representa uma chapa; registre uma operação por chapa.")
            if not chapa:
                self.add_error("chapa_estoque", "Selecione uma chapa ou sobra disponível.")
            elif material and chapa.material_id != material.pk:
                self.add_error("chapa_estoque", "A chapa selecionada é de outro material.")
        if origem == OperacaoCorte.Origem.MANUAL and chapa:
            self.add_error("chapa_estoque", "Retire a chapa selecionada ou escolha origem pelo estoque.")
        return dados


class PecaCortadaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PecaCortada
        fields = ["identificacao", "largura_mm", "altura_mm", "quantidade"]
        widgets = {"largura_mm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}), "altura_mm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}), "quantidade": forms.NumberInput(attrs={"min": "1", "step": "1"})}


class SobraForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Sobra
        fields = ["largura_mm", "altura_mm", "observacoes"]
        widgets = {"largura_mm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}), "altura_mm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"})}


PecaFormSet = inlineformset_factory(OperacaoCorte, PecaCortada, form=PecaCortadaForm, extra=1, can_delete=True)
SobraFormSet = inlineformset_factory(OperacaoCorte, Sobra, form=SobraForm, extra=1, can_delete=True)
