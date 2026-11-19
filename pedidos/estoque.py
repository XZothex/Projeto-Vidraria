"""Consultas de saldo para os pedidos."""
from decimal import Decimal

from django.db.models import Sum

from . import estoque_mysql
from .models import Reserva


def saldo_fisico(material):
    """Quantidade física na unidade do material, quando há integração ativa."""
    if estoque_mysql.ativo():
        return estoque_mysql.saldos(material)[0]
    return None


def quantidade_reservada(material):
    """Soma das reservas ATIVAS de todos os pedidos para o material."""
    if estoque_mysql.ativo():
        return estoque_mysql.saldos(material)[1]
    total = Reserva.objects.filter(item__material=material, status=Reserva.Status.ATIVA).aggregate(
        total=Sum("quantidade")
    )["total"]
    return total or Decimal("0")


def quantidade_disponivel(material):
    """Saldo físico menos o já reservado; ``None`` quando não há controle de saldo."""
    if estoque_mysql.ativo():
        fisico, reservado = estoque_mysql.saldos(material)
        return fisico - reservado
    saldo = saldo_fisico(material)
    if saldo is None:
        return None
    return saldo - quantidade_reservada(material)
