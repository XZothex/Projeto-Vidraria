"""Baixa do lote reservado e entrada de sobras na transação do corte."""
from django.core.exceptions import ValidationError
from django.db import connection

from pedidos.models import Reserva


def _lotes_reservados(cursor, ids, *, travar=False):
    if not ids:
        return []
    marcadores = ", ".join(["%s"] * len(ids))
    bloqueio = " FOR UPDATE" if travar else ""
    cursor.execute(
        "SELECT r.id_reserva, r.quantidade, e.id_estoque, e.id_material, "
        "e.largura_mm, e.altura_mm, e.localizacao, m.espessura_mm "
        "FROM reserva r JOIN estoque e ON e.id_estoque = r.id_estoque "
        "JOIN material m ON m.id_material = e.id_material "
        f"WHERE r.id_reserva IN ({marcadores}) AND r.status IN ('ativa', 'separada') "
        "AND m.unidade = 'chapa' AND e.largura_mm IS NOT NULL AND e.altura_mm IS NOT NULL "
        f"ORDER BY e.id_estoque, r.id_reserva{bloqueio}",
        ids,
    )
    return cursor.fetchall()


def opcoes_lote():
    reservas = Reserva.objects.filter(
        status=Reserva.Status.ATIVA, item__pedido__status="aberto", item__material__ativo=True,
        item__material__categoria="vidro",
    ).select_related("item__pedido", "item__material")
    itens = {id_reserva: reserva.item for reserva in reservas for id_reserva in reserva.mysql_reservas}
    with connection.cursor() as cursor:
        lotes = _lotes_reservados(cursor, list(itens))
    return [
        (id_reserva, f"{itens[id_reserva].pedido.numero} · {itens[id_reserva].material.codigo} "
                     f"· item {itens[id_reserva].pk} · lote #{id_lote} · {qtd:.0f} chapa(s) · {largura} × {altura} mm")
        for id_reserva, qtd, id_lote, _, largura, altura, _, _ in lotes
    ]


def preparar(cursor, operacao, usuario, id_reserva_mysql=None):
    reserva = Reserva.objects.filter(item_id=operacao.item_pedido_id, status=Reserva.Status.ATIVA).first()
    if reserva is None or not reserva.mysql_reservas:
        raise ValidationError("Reserve as chapas deste item antes de registrar o corte.")
    if id_reserva_mysql is not None and id_reserva_mysql not in reserva.mysql_reservas:
        raise ValidationError("O lote selecionado não pertence à reserva deste item.")
    ids = [id_reserva_mysql] if id_reserva_mysql is not None else reserva.mysql_reservas
    lotes = _lotes_reservados(cursor, ids, travar=True)
    if not lotes:
        raise ValidationError("Selecione uma reserva ainda sem corte, em um lote de chapas com dimensões cadastradas.")
    if len(lotes) > 1:
        raise ValidationError("Selecione o lote a cortar. Registre um corte para cada lote reservado.")
    id_reserva, qtd, id_lote, id_material, largura, altura, local, espessura = lotes[0]
    if qtd != qtd.to_integral_value() or qtd > reserva.quantidade:
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
