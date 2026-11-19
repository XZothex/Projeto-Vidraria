"""Baixa do lote reservado e entrada de sobras na transação do corte."""
from django.core.exceptions import ValidationError
from django.db import connection

from pedidos.models import Reserva


def preparar(cursor, operacao, usuario):
    reserva = Reserva.objects.filter(item_id=operacao.item_pedido_id, status=Reserva.Status.ATIVA).first()
    if reserva is None or len(reserva.mysql_reservas) != 1:
        raise ValidationError("Reserve as chapas deste item em um único lote MySQL antes de registrar o corte.")
    cursor.execute(
        "SELECT r.id_reserva, r.status, r.quantidade, e.id_estoque, "
        "e.id_material, e.largura_mm, e.altura_mm, e.localizacao, m.espessura_mm, m.unidade "
        "FROM reserva r JOIN estoque e ON e.id_estoque = r.id_estoque "
        "JOIN material m ON m.id_material = e.id_material WHERE r.id_reserva = %s FOR UPDATE",
        reserva.mysql_reservas,
    )
    registro = cursor.fetchone()
    if registro is None:
        raise ValidationError("O lote reservado não foi encontrado no MySQL.")
    id_reserva, status, qtd, id_lote, id_material, largura, altura, local, espessura, unidade = registro
    if status not in {"ativa", "separada"} or unidade != "chapa" or not largura or not altura:
        raise ValidationError("Selecione uma reserva ainda sem corte, em um lote de chapas com dimensões cadastradas.")
    if qtd != qtd.to_integral_value() or qtd != reserva.quantidade:
        raise ValidationError("A quantidade de chapas do lote diverge da reserva do pedido.")
    cursor.execute("SELECT id_usuario, perfil FROM usuario WHERE login = %s", [usuario.get_username()])
    responsavel = cursor.fetchone()
    if responsavel is None or responsavel[1] not in {"administracao", "estoque", "producao"}:
        raise ValidationError("Seu usuário precisa de um perfil de administração, estoque ou produção no MySQL.")
    operacao.largura_chapa_mm = largura
    operacao.altura_chapa_mm = altura
    operacao.espessura_mm = espessura
    operacao.quantidade_chapas = int(qtd)
    return id_reserva, qtd, id_lote, id_material, local, responsavel[0]


def baixar(alocacao, sobras):
    id_reserva, quantidade, id_lote, id_material, local, id_usuario = alocacao
    with connection.cursor() as cursor:
        cursor.execute("UPDATE reserva SET status = 'cortada' WHERE id_reserva = %s", [id_reserva])
        cursor.execute(
            "INSERT INTO movimentacao (id_estoque, id_reserva, id_usuario, tipo, quantidade) "
            "VALUES (%s, %s, %s, 'corte', %s)", [id_lote, id_reserva, id_usuario, -quantidade],
        )
        ids = []
        for sobra in sobras:
            largura, altura = sobra["largura_mm"], sobra["altura_mm"]
            if largura != int(largura) or altura != int(altura):
                raise ValidationError("As dimensões das sobras para o MySQL devem ser em milímetros inteiros.")
            cursor.execute(
                "INSERT INTO estoque (id_material, id_lote_origem, localizacao, origem, largura_mm, altura_mm) "
                "VALUES (%s, %s, %s, 'sobra', %s, %s)", [id_material, id_lote, local, largura, altura],
            )
            ids.append(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO movimentacao (id_estoque, id_usuario, tipo, quantidade) VALUES (%s, %s, 'sobra', 1)",
                [ids[-1], id_usuario],
            )
    return ids
