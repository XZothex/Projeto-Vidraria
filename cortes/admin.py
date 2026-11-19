from django.contrib import admin
from django.db import connection
from .models import ChapaDisponivel, OperacaoCorte, PecaCortada, Sobra


class HistoricoSomenteLeitura:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PecaInline(HistoricoSomenteLeitura, admin.TabularInline):
    model = PecaCortada
    extra = 0


class SobraInline(HistoricoSomenteLeitura, admin.TabularInline):
    model = Sobra
    extra = 0


@admin.register(OperacaoCorte)
class OperacaoCorteAdmin(HistoricoSomenteLeitura, admin.ModelAdmin):
    list_display = ("id", "pedido", "material", "origem", "realizado_em", "realizado_por")
    list_filter = ("origem", "realizado_em")
    search_fields = ("pedido__cliente__nome", "material__nome")
    inlines = (PecaInline, SobraInline)


@admin.register(ChapaDisponivel)
class ChapaDisponivelAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "material", "tipo", "largura_mm", "altura_mm", "status")
    list_filter = ("tipo", "status", "material")
    search_fields = ("codigo", "material__nome")


    def has_module_permission(self, request):
        return connection.vendor != "mysql" and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return connection.vendor != "mysql" and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return connection.vendor != "mysql" and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return connection.vendor != "mysql" and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return connection.vendor != "mysql" and super().has_delete_permission(request, obj)
