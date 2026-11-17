from django.contrib import admin

from .models import Cliente, Entrega, ItemPedido, Pedido, Reserva


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Registros não são apagados (histórico); estados mudam pelo sistema, com as regras de negócio."""

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cliente)
class ClienteAdmin(SomenteLeituraAdmin):
    list_display = ("nome", "cpf_cnpj", "telefone", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "cpf_cnpj")


class ItemInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    can_delete = False
    readonly_fields = ("material", "quantidade", "especificacao")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(SomenteLeituraAdmin):
    list_display = ("pk", "cliente", "status", "data_prevista", "criado_em")
    list_filter = ("status",)
    search_fields = ("cliente__nome",)
    readonly_fields = ("cliente", "status", "criado_por", "criado_em", "cancelado_em", "cancelado_por", "motivo_cancelamento")
    inlines = [ItemInline]

    def has_add_permission(self, request):
        return False


@admin.register(Reserva)
class ReservaAdmin(SomenteLeituraAdmin):
    list_display = ("item", "quantidade", "status", "criada_em", "encerrada_em")
    list_filter = ("status",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Entrega)
class EntregaAdmin(SomenteLeituraAdmin):
    list_display = ("pedido", "data_entrega", "recebido_por", "registrado_por")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
