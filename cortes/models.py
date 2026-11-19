from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from cadastros.models import Material
from pedidos.models import ItemPedido, Pedido


class ChapaDisponivel(models.Model):
    """Unidade física disponível para corte; também armazena sobras reaproveitáveis.

    Este cadastro local permite testar o fluxo enquanto o módulo geral de entradas
    (etapa 4) não estiver integrado. A integração futura deve alimentar este modelo
    por serviço, sem alterar os modelos de cadastros ou pedidos.
    """
    class Tipo(models.TextChoices):
        CHAPA = "chapa", "Chapa inteira"
        SOBRA = "sobra", "Sobra reaproveitável"

    class Status(models.TextChoices):
        DISPONIVEL = "disponivel", "Disponível"
        RESERVADA = "reservada", "Reservada"
        CONSUMIDA = "consumida", "Consumida"
        INATIVA = "inativa", "Inativa"

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="chapas_corte")
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.CHAPA)
    largura_mm = models.DecimalField("Largura (mm)", max_digits=10, decimal_places=2)
    altura_mm = models.DecimalField("Altura (mm)", max_digits=10, decimal_places=2)
    espessura_mm = models.DecimalField("Espessura (mm)", max_digits=6, decimal_places=2, null=True, blank=True)
    codigo = models.CharField("Identificação", max_length=40, blank=True, db_index=True)
    origem_descricao = models.CharField("Origem / observação", max_length=180, blank=True)
    sobra_de = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="sobras_geradas")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DISPONIVEL, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["material__nome", "-criado_em"]
        constraints = [
            models.CheckConstraint(condition=Q(largura_mm__gt=0), name="chapa_largura_positiva"),
            models.CheckConstraint(condition=Q(altura_mm__gt=0), name="chapa_altura_positiva"),
            models.CheckConstraint(condition=Q(espessura_mm__isnull=True) | Q(espessura_mm__gt=0), name="chapa_espessura_positiva"),
        ]

    def __str__(self):
        return f"{self.material} — {self.largura_mm} x {self.altura_mm} mm ({self.get_status_display()})"

    @property
    def area_mm2(self):
        return self.largura_mm * self.altura_mm


class OperacaoCorte(models.Model):
    class Origem(models.TextChoices):
        ESTOQUE = "estoque", "Chapa/sobra cadastrada no estoque"
        MANUAL = "manual", "Informar chapa manualmente"
        MYSQL = "mysql", "Lote reservado no MySQL"

    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name="operacoes_corte")
    item_pedido = models.ForeignKey(ItemPedido, on_delete=models.PROTECT, related_name="operacoes_corte")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="operacoes_corte")
    origem = models.CharField(max_length=10, choices=Origem.choices)
    chapa_estoque = models.ForeignKey(ChapaDisponivel, null=True, blank=True, on_delete=models.PROTECT, related_name="operacoes_corte")
    largura_chapa_mm = models.DecimalField("Largura da chapa (mm)", max_digits=10, decimal_places=2, null=True, blank=True)
    altura_chapa_mm = models.DecimalField("Altura da chapa (mm)", max_digits=10, decimal_places=2, null=True, blank=True)
    espessura_mm = models.DecimalField("Espessura (mm)", max_digits=6, decimal_places=2, null=True, blank=True)
    quantidade_chapas = models.PositiveIntegerField("Quantidade de chapas", default=1)
    kerf_mm = models.DecimalField("Perda por corte (mm)", max_digits=5, decimal_places=2, default=Decimal("3.00"))
    observacoes = models.TextField(blank=True)
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cortes_realizados")
    realizado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-realizado_em", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(largura_chapa_mm__gt=0), name="corte_largura_positiva"),
            models.CheckConstraint(condition=Q(altura_chapa_mm__gt=0), name="corte_altura_positiva"),
            models.CheckConstraint(condition=Q(quantidade_chapas__gt=0), name="corte_qtd_chapas_positiva"),
            models.CheckConstraint(condition=Q(kerf_mm__gte=0), name="corte_kerf_nao_negativo"),
        ]

    def clean(self):
        erros = {}
        if self.largura_chapa_mm is not None and self.largura_chapa_mm <= 0:
            erros["largura_chapa_mm"] = "A largura da chapa deve ser maior que zero."
        if self.altura_chapa_mm is not None and self.altura_chapa_mm <= 0:
            erros["altura_chapa_mm"] = "A altura da chapa deve ser maior que zero."
        if self.item_pedido_id and self.pedido_id and self.item_pedido.pedido_id != self.pedido_id:
            erros["item_pedido"] = "O item selecionado não pertence ao pedido informado."
        if self.item_pedido_id and self.material_id and self.item_pedido.material_id != self.material_id:
            erros["material"] = "O material deve ser o mesmo do item do pedido."
        if self.origem == self.Origem.ESTOQUE:
            if not self.chapa_estoque_id:
                erros["chapa_estoque"] = "Selecione uma chapa ou sobra disponível."
            elif self.chapa_estoque.status != ChapaDisponivel.Status.DISPONIVEL:
                erros["chapa_estoque"] = "A chapa selecionada não está disponível."
            elif self.chapa_estoque.material_id != self.material_id:
                erros["chapa_estoque"] = "A chapa selecionada pertence a outro material."
        elif self.chapa_estoque_id:
            erros["chapa_estoque"] = "Não selecione chapa do estoque quando a origem for manual."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f"Corte #{self.pk or 'novo'} — {self.pedido}"


class PecaCortada(models.Model):
    operacao = models.ForeignKey(OperacaoCorte, on_delete=models.PROTECT, related_name="pecas")
    identificacao = models.CharField("Identificação da peça", max_length=100, blank=True)
    largura_mm = models.DecimalField("Largura (mm)", max_digits=10, decimal_places=2)
    altura_mm = models.DecimalField("Altura (mm)", max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(largura_mm__gt=0), name="peca_largura_positiva"),
            models.CheckConstraint(condition=Q(altura_mm__gt=0), name="peca_altura_positiva"),
            models.CheckConstraint(condition=Q(quantidade__gt=0), name="peca_qtd_positiva"),
        ]

    @property
    def area_total_mm2(self):
        return self.largura_mm * self.altura_mm * self.quantidade


class Sobra(models.Model):
    class Status(models.TextChoices):
        DISPONIVEL = "disponivel", "Disponível"
        RESERVADA = "reservada", "Reservada"
        UTILIZADA = "utilizada", "Utilizada"
        DESCARTADA = "descartada", "Descartada"

    operacao = models.ForeignKey(OperacaoCorte, on_delete=models.PROTECT, related_name="sobras")
    chapa_gerada = models.OneToOneField(ChapaDisponivel, null=True, blank=True, on_delete=models.PROTECT, related_name="registro_sobra")
    mysql_lote_id = models.PositiveIntegerField(null=True, blank=True, editable=False)
    largura_mm = models.DecimalField("Largura (mm)", max_digits=10, decimal_places=2)
    altura_mm = models.DecimalField("Altura (mm)", max_digits=10, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DISPONIVEL)
    observacoes = models.CharField(max_length=180, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(largura_mm__gt=0), name="sobra_largura_positiva"),
            models.CheckConstraint(condition=Q(altura_mm__gt=0), name="sobra_altura_positiva"),
        ]
