from django.contrib import admin

from .models import Fornecedor, Material


class SemExclusaoAdmin(admin.ModelAdmin):
    """Registros são inativados, nunca apagados (outros módulos podem usá-los)."""

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Material)
class MaterialAdmin(SemExclusaoAdmin):
    list_display = ("codigo", "nome", "categoria", "unidade_controle", "ativo")
    list_filter = ("categoria", "ativo")
    search_fields = ("codigo", "nome")


@admin.register(Fornecedor)
class FornecedorAdmin(SemExclusaoAdmin):
    list_display = ("nome", "cpf_cnpj", "telefone", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "nome_fantasia", "cpf_cnpj")
