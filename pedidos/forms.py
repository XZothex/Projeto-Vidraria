from django import forms
from django.utils import timezone

from cadastros.forms import BootstrapFormMixin
from cadastros.models import Material
from cadastros.validators import somente_digitos, validar_cpf_cnpj

from .models import Cliente, ItemPedido, Pedido


class ClienteForm(BootstrapFormMixin, forms.ModelForm):
    # Declarados aqui para aceitar pontuação (o modelo guarda só os dígitos).
    cpf_cnpj = forms.CharField(
        label="CPF/CNPJ", required=False, max_length=18, help_text="Opcional. Com ou sem pontuação."
    )
    telefone = forms.CharField(label="Telefone", max_length=20, help_text="Com DDD. Ex.: (11) 98888-7777")

    class Meta:
        model = Cliente
        fields = ["nome", "cpf_cnpj", "telefone", "email", "endereco", "observacoes", "ativo"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def clean_cpf_cnpj(self):
        valor = self.cleaned_data.get("cpf_cnpj")
        if valor:
            validar_cpf_cnpj(valor)
        digitos = somente_digitos(valor)
        if not digitos:
            return None  # opcional: vazio vira NULL
        existentes = Cliente.objects.filter(cpf_cnpj=digitos)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError("Já existe um cliente com este CPF/CNPJ.")
        return digitos

    def clean_telefone(self):
        return somente_digitos(self.cleaned_data["telefone"])


class PedidoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ["cliente", "data_prevista", "observacoes"]
        widgets = {
            "data_prevista": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Só clientes ativos; na edição, mantém o cliente atual mesmo que tenha sido inativado.
        clientes = Cliente.objects.filter(ativo=True)
        if self.instance.pk:
            clientes = Cliente.objects.filter(ativo=True) | Cliente.objects.filter(pk=self.instance.cliente_id)
        self.fields["cliente"].queryset = clientes.order_by("nome")

    def clean_data_prevista(self):
        data = self.cleaned_data.get("data_prevista")
        if data and "data_prevista" in self.changed_data and data < timezone.localdate():
            raise forms.ValidationError("A data prevista não pode estar no passado.")
        return data


class ItemPedidoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemPedido
        fields = ["material", "quantidade", "especificacao"]
        widgets = {"quantidade": forms.NumberInput(attrs={"step": "any", "min": "0.001"})}

    def __init__(self, *args, pedido, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.pedido = pedido
        materiais = Material.objects.filter(ativo=True)
        if self.instance.pk:
            materiais = materiais | Material.objects.filter(pk=self.instance.material_id)
        self.fields["material"].queryset = materiais.order_by("nome", "codigo")
        self.fields["quantidade"].help_text = "Na unidade de controle do material (chapa, peça, metro ou m²)."

    def clean(self):
        dados = super().clean()
        material, quantidade = dados.get("material"), dados.get("quantidade")
        if material and quantidade is not None and material.unidade_controle in (
            Material.Unidade.CHAPA, Material.Unidade.UNIDADE
        ):
            if quantidade != quantidade.to_integral_value():
                self.add_error("quantidade", "Este material é controlado por unidade inteira (chapa/peça).")
        return dados


class CancelamentoForm(BootstrapFormMixin, forms.Form):
    motivo = forms.CharField(label="Motivo do cancelamento", widget=forms.Textarea(attrs={"rows": 3}))

    def clean_motivo(self):
        return self.cleaned_data["motivo"].strip()


class EntregaForm(BootstrapFormMixin, forms.Form):
    data_entrega = forms.DateField(
        label="Data da entrega", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    recebido_por = forms.CharField(label="Recebido por", max_length=150)
    observacoes = forms.CharField(label="Observações", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_entrega"].initial = timezone.localdate()

    def clean_data_entrega(self):
        data = self.cleaned_data["data_entrega"]
        if data > timezone.localdate():
            raise forms.ValidationError("A data da entrega não pode ser futura.")
        return data
