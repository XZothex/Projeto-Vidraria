from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import connection

from cadastros.forms import BootstrapFormMixin

PERFIS_MYSQL = [("vendas", "Vendas"), ("estoque", "Estoque"), ("producao", "Produção")]


class ContaForm(BootstrapFormMixin, UserCreationForm):
    administrador = forms.BooleanField(label="Administrador", required=False)

    class Meta(UserCreationForm.Meta):
        fields = ("username", "first_name", "last_name")
        labels = {"first_name": "Nome", "last_name": "Sobrenome"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        if connection.vendor == "mysql":
            self.fields["perfil_mysql"] = forms.ChoiceField(
                label="Perfil no estoque", choices=PERFIS_MYSQL, initial="vendas", required=False,
                help_text="Administradores recebem o perfil Administração.",
                widget=forms.Select(attrs={"class": "form-select"}),
            )

    def clean(self):
        dados = super().clean()
        if connection.vendor == "mysql":
            if not dados.get("administrador") and not dados.get("perfil_mysql"):
                self.add_error("perfil_mysql", "Selecione o perfil no estoque.")
            if len(dados.get("username", "")) > 50:
                self.add_error("username", "Use até 50 caracteres para o login do estoque.")
            nome = " ".join(filter(None, [dados.get("first_name"), dados.get("last_name")]))
            if len(nome) > 150:
                self.add_error("first_name", "O nome completo deve ter até 150 caracteres.")
        return dados
