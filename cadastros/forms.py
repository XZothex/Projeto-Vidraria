from django import forms

from .models import Fornecedor, Material
from .validators import somente_digitos, validar_cpf_cnpj


class BootstrapFormMixin:
    """Aplica classes do Bootstrap aos campos e marca os campos com erro."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                classe = "form-check-input"
            elif isinstance(widget, forms.Select):
                classe = "form-select"
            else:
                classe = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {classe}".strip()

    def full_clean(self):
        super().full_clean()
        if self.is_bound:
            for nome in self.errors:
                if nome in self.fields:
                    widget = self.fields[nome].widget
                    widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class MaterialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Material
        fields = [
            "codigo", "nome", "categoria", "descricao", "tipo_vidro", "cor",
            "espessura_mm", "unidade_controle", "localizacao_padrao", "ativo",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "espessura_mm": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }
        help_texts = {
            "codigo": "Identificação única do material. Ex.: VID-TEMP-8-INC",
            "tipo_vidro": "Preencha somente se o material for vidro.",
            "cor": "Preencha somente se aplicável.",
            "espessura_mm": "Em milímetros. Preencha somente se aplicável.",
            "ativo": "Materiais inativos não somem do histórico, apenas deixam de ser oferecidos.",
        }

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip().upper()
        existentes = Material.objects.filter(codigo__iexact=codigo)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError("Já existe um material com este código.")
        return codigo


class FornecedorForm(BootstrapFormMixin, forms.ModelForm):
    # Declarados aqui para aceitar pontuação (o modelo guarda só os dígitos).
    cpf_cnpj = forms.CharField(
        label="CPF/CNPJ", required=False, max_length=18, help_text="Opcional. Com ou sem pontuação."
    )
    telefone = forms.CharField(
        label="Telefone", max_length=20, help_text="Com DDD. Ex.: (11) 98888-7777"
    )

    class Meta:
        model = Fornecedor
        fields = [
            "nome", "nome_fantasia", "cpf_cnpj", "telefone", "email",
            "endereco", "observacoes", "ativo",
        ]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def clean_cpf_cnpj(self):
        valor = self.cleaned_data.get("cpf_cnpj")
        if valor:
            validar_cpf_cnpj(valor)
        digitos = somente_digitos(valor)
        if not digitos:
            return None  # opcional: vazio vira NULL
        validar_cpf_cnpj(digitos)
        existentes = Fornecedor.objects.filter(cpf_cnpj=digitos)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError("Já existe um fornecedor com este CPF/CNPJ.")
        return digitos

    def clean_telefone(self):
        return somente_digitos(self.cleaned_data["telefone"])
