from django import forms

from cadastros.forms import BootstrapFormMixin
from cadastros.validators import somente_digitos, validar_cpf_cnpj

from .models import Cliente


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
