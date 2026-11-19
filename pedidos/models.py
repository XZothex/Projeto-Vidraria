"""Modelos do módulo de pedidos e reservas.

Decisões de modelagem:

* ``Cliente`` fica aqui (e não em ``cadastros``) para não conflitar com o módulo
  de materiais/fornecedores. Segue as mesmas regras: nada é apagado, só inativado.
* ``Pedido`` tem um ciclo de vida simples: ABERTO -> ENTREGUE ou ABERTO -> CANCELADO.
  Pedidos entregues ou cancelados ficam somente para consulta.
* ``ItemPedido`` pede uma quantidade de um ``Material`` (tipo de material, não peça física).
* ``Reserva`` é o registro histórico de que a quantidade de um item foi separada:
  ATIVA (separada) -> LIBERADA (devolvida ao disponível) ou CONSUMIDA (saiu na entrega).
  Só pode haver uma reserva ATIVA por item (restrição no banco).
* ``Entrega`` registra quando, para quem e por quem o pedido foi entregue.
* O saldo físico NÃO existe aqui: é responsabilidade do módulo de estoque. O ponto de
  integração é ``pedidos/estoque.py``.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from cadastros.models import Material
from cadastros.validators import (
    formatar_cpf_cnpj,
    formatar_telefone,
    somente_digitos,
    validar_cpf_cnpj,
    validar_positivo,
    validar_telefone,
)


class Cliente(models.Model):
    nome = models.CharField("Nome / razão social", max_length=150)
    # Só dígitos. NULL (e não "") quando vazio, para vários clientes sem documento.
    cpf_cnpj = models.CharField(
        "CPF/CNPJ", max_length=14, unique=True, null=True, blank=True, validators=[validar_cpf_cnpj]
    )
    telefone = models.CharField("Telefone", max_length=15, validators=[validar_telefone])
    email = models.EmailField("E-mail", blank=True)
    endereco = models.CharField("Endereço", max_length=255, blank=True)
    observacoes = models.TextField("Observações", blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.cpf_cnpj = somente_digitos(self.cpf_cnpj) or None
        self.telefone = somente_digitos(self.telefone)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("pedidos:cliente_detail", args=[self.pk])

    @property
    def cpf_cnpj_formatado(self):
        return formatar_cpf_cnpj(self.cpf_cnpj)

    @property
    def telefone_formatado(self):
        return formatar_telefone(self.telefone)


class Pedido(models.Model):
    class Status(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        ENTREGUE = "entregue", "Entregue"
        CANCELADO = "cancelado", "Cancelado"

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="pedidos", verbose_name="Cliente")
    status = models.CharField("Situação", max_length=10, choices=Status.choices, default=Status.ABERTO, db_index=True)
    data_prevista = models.DateField("Entrega prevista", null=True, blank=True)
    observacoes = models.TextField("Observações", blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="Criado por", editable=False,
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    cancelado_em = models.DateTimeField("Cancelado em", null=True, blank=True)
    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="Cancelado por",
    )
    motivo_cancelamento = models.TextField("Motivo do cancelamento", blank=True)

    mysql_pedido_id = models.PositiveIntegerField(null=True, blank=True, editable=False, unique=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def __str__(self):
        return f"Pedido {self.numero}"

    def get_absolute_url(self):
        return reverse("pedidos:pedido_detail", args=[self.pk])

    @property
    def numero(self):
        return f"#{self.pk:05d}" if self.pk else "(novo)"

    @property
    def aberto(self):
        return self.status == self.Status.ABERTO


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="itens_pedido", verbose_name="Material")
    quantidade = models.DecimalField(
        "Quantidade", max_digits=10, decimal_places=3, validators=[validar_positivo]
    )
    especificacao = models.CharField(
        "Especificação", max_length=200, blank=True,
        help_text="Medidas, acabamento, furos etc. Ex.: 80 x 120 cm, 2 furos.",
    )

    class Meta:
        ordering = ["pk"]
        verbose_name = "item do pedido"
        verbose_name_plural = "itens do pedido"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantidade__gt=0), name="item_pedido_quantidade_positiva"),
        ]

    def __str__(self):
        return f"{self.quantidade} x {self.material}"

    @property
    def reserva_ativa(self):
        """Reserva ativa do item (usa o cache de prefetch quando disponível)."""
        for reserva in self.reservas.all():
            if reserva.status == Reserva.Status.ATIVA:
                return reserva
        return None

    @property
    def reservado(self):
        return self.reserva_ativa is not None


class Reserva(models.Model):

    class Status(models.TextChoices):
        ATIVA = "ativa", "Ativa"
        LIBERADA = "liberada", "Liberada"
        CONSUMIDA = "consumida", "Consumida (entregue)"

    item = models.ForeignKey(ItemPedido, on_delete=models.CASCADE, related_name="reservas")
    quantidade = models.DecimalField("Quantidade", max_digits=10, decimal_places=3)
    status = models.CharField("Situação", max_length=10, choices=Status.choices, default=Status.ATIVA, db_index=True)
    criada_em = models.DateTimeField("Reservada em", auto_now_add=True)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    mysql_reservas = models.JSONField(default=list, blank=True, editable=False)
    item_com_reserva_ativa = models.GeneratedField(
        expression=models.Case(models.When(status="ativa", then=models.F("item_id"))),
        output_field=models.BigIntegerField(),
        db_persist=True,
        null=True,
        unique=True,
    )
    encerrada_em = models.DateTimeField("Encerrada em", null=True, blank=True)
    encerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-criada_em", "-pk"]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantidade__gt=0), name="reserva_quantidade_positiva"),
        ]

    def __str__(self):
        return f"Reserva {self.get_status_display()} de {self.quantidade} ({self.item.material})"


class Entrega(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.PROTECT, related_name="entrega")
    data_entrega = models.DateField("Data da entrega")
    recebido_por = models.CharField("Recebido por", max_length=150)
    observacoes = models.TextField("Observações", blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    registrado_em = models.DateTimeField("Registrada em", auto_now_add=True)

    class Meta:
        verbose_name = "entrega"
        verbose_name_plural = "entregas"

    def __str__(self):
        return f"Entrega do {self.pedido}"
