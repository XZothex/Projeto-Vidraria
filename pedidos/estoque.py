"""PONTO ÚNICO DE INTEGRAÇÃO com o módulo de estoque.

O módulo de estoque (entradas, chapas, sobras) ainda não existe, então hoje não há
saldo físico para comparar. Enquanto ``saldo_fisico`` devolver ``None``, as reservas
são registradas SEM validar disponibilidade (o sistema só controla o que está
reservado). Quando o estoque existir, basta implementar ``saldo_fisico`` aqui:
a partir daí, reservar acima do disponível passa a ser recusado automaticamente.
"""
from decimal import Decimal

from django.db.models import Sum

from .models import Reserva


def saldo_fisico(material):
    """Quantidade fisicamente em estoque, em CHAPAS (decisão da equipe: o saldo é por chapa).

    Deve ser expressa na mesma unidade da quantidade pedida, ou seja, em
    ``material.unidade_controle``. Para materiais controlados por chapa
    (``Material.Unidade.CHAPA``) isso já é direto. Materiais cadastrados em m² ou metro
    NÃO são comparáveis com um saldo em chapas: ou o cadastro passa a usar "chapa" para
    eles, ou este módulo precisa converter (ex.: área da chapa) antes de comparar.

    Devolve ``None`` enquanto não houver controle de saldo (ou para materiais que o
    estoque não controla por chapa): nesse caso a reserva é aceita sem checar disponibilidade.
    TODO: integrar com o módulo de estoque.
    """
    return None


def quantidade_reservada(material):
    """Soma das reservas ATIVAS de todos os pedidos para o material."""
    total = Reserva.objects.filter(item__material=material, status=Reserva.Status.ATIVA).aggregate(
        total=Sum("quantidade")
    )["total"]
    return total or Decimal("0")


def quantidade_disponivel(material):
    """Saldo físico menos o já reservado; ``None`` quando não há controle de saldo."""
    saldo = saldo_fisico(material)
    if saldo is None:
        return None
    return saldo - quantidade_reservada(material)
