"""Integra pedidos ao esquema SQL usando a mesma transação do Django."""
from decimal import Decimal

from django.db import connection

UNIDADES = {"chapa": "chapa", "unidade": "peca", "metro": "metro", "m2": "m2"}


class ErroEstoque(Exception):
    """Operação incompatível com o estoque compartilhado."""


def ativo():
    return connection.vendor == "mysql"


def _material(cursor, material):
    cursor.execute(
        "SELECT id_material, unidade FROM material WHERE codigo = %s",
        [material.codigo],
    )
    registro = cursor.fetchone()
    if registro is None:
        raise ErroEstoque(f"Cadastre {material.codigo} também no estoque MySQL.")
    id_material, unidade = registro
    if unidade != UNIDADES.get(material.unidade_controle):
        raise ErroEstoque(f"A unidade do material {material.codigo} difere entre os cadastros.")
    return id_material


def saldos(material):
    with connection.cursor() as cursor:
        try:
            id_material = _material(cursor, material)
        except ErroEstoque:
            return Decimal(0), Decimal(0)
        cursor.execute(
            "SELECT COALESCE(SUM(saldo_fisico), 0), COALESCE(SUM(saldo_reservado), 0) "
            "FROM estoque WHERE id_material = %s AND origem <> 'sobra'",
            [id_material],
        )
        return cursor.fetchone()


def _usuario(cursor, usuario):
    cursor.execute("SELECT id_usuario FROM usuario WHERE login = %s", [usuario.get_username()])
    registro = cursor.fetchone()
    if registro is None:
        raise ErroEstoque("Cadastre seu login do Django também na tabela usuario do estoque MySQL.")
    return registro[0]


def _pedido(cursor, pedido):
    if pedido.mysql_pedido_id is None:
        cliente = pedido.cliente
        cursor.execute(
            "INSERT INTO cliente (nome, telefone, email) VALUES (%s, %s, %s)",
            [cliente.nome, cliente.telefone or None, cliente.email or None],
        )
        id_cliente = cursor.lastrowid
        cursor.execute(
            "INSERT INTO pedido (id_cliente, data_pedido, status) VALUES (%s, CURRENT_DATE, 'confirmado')",
            [id_cliente],
        )
        pedido.mysql_pedido_id = cursor.lastrowid
        pedido.save(update_fields=["mysql_pedido_id"])
    return pedido.mysql_pedido_id


def reservar(pedido, itens, usuario):
    """Aloca a quantidade de cada item em lotes de compra na ordem de cadastro."""
    with connection.cursor() as cursor:
        materiais = {item.material_id: item.material for item in itens}
        ids = {pk: _material(cursor, material) for pk, material in materiais.items()}
        lotes = {}
        for id_material in sorted(set(ids.values())):
            # A trava do cadastro serializa a escolha de lotes do mesmo material.
            cursor.execute("SELECT id_material FROM material WHERE id_material = %s FOR UPDATE", [id_material])
            cursor.fetchone()
            cursor.execute(
                "SELECT id_estoque, saldo_fisico - saldo_reservado FROM estoque "
                "WHERE id_material = %s AND origem <> 'sobra' ORDER BY id_estoque FOR UPDATE",
                [id_material],
            )
            lotes[id_material] = [list(lote) for lote in cursor.fetchall()]

        id_usuario = _usuario(cursor, usuario)
        id_pedido = _pedido(cursor, pedido)
        alocacoes = []
        for item in itens:
            id_material = ids[item.material_id]
            pendente = item.quantidade
            disponivel = sum((saldo for _, saldo in lotes[id_material]), Decimal(0))
            if pendente > disponivel:
                raise ErroEstoque(f"Disponibilidade insuficiente para {item.material.codigo}: "
                                  f"necessário {pendente}, disponível {disponivel}.")
            cursor.execute(
                "INSERT INTO item_pedido (id_pedido, id_material, quantidade, preco_unitario) "
                "VALUES (%s, %s, %s, 0)",
                [id_pedido, id_material, pendente],
            )
            id_item = cursor.lastrowid
            reservas = []
            for lote in lotes[id_material]:
                quantidade = min(lote[1], pendente)
                if not quantidade:
                    continue
                cursor.execute(
                    "INSERT INTO reserva (id_item, id_estoque, id_material, id_usuario, quantidade) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [id_item, lote[0], id_material, id_usuario, quantidade],
                )
                reservas.append(cursor.lastrowid)
                lote[1] -= quantidade
                pendente -= quantidade
                if not pendente:
                    break
            alocacoes.append(reservas)
        return alocacoes


def encerrar(reservas, usuario, *, entrega=False):
    ids = []
    for reserva in reservas:
        if not reserva.mysql_reservas:
            # Reservas antigas podem ser liberadas para refazer a alocação.
            if entrega:
                raise ErroEstoque("Libere e refaça as reservas antigas antes de entregar pelo MySQL.")
        ids.extend(reserva.mysql_reservas)
    if not ids:
        return
    with connection.cursor() as cursor:
        id_usuario = _usuario(cursor, usuario) if entrega else None
        marcadores = ", ".join(["%s"] * len(ids))
        cursor.execute(
            f"SELECT id_reserva, id_estoque, status, quantidade FROM reserva "
            f"WHERE id_reserva IN ({marcadores}) ORDER BY id_estoque, id_reserva FOR UPDATE",
            ids,
        )
        registros = cursor.fetchall()
        if len(registros) != len(ids):
            raise ErroEstoque("Uma reserva vinculada não foi encontrada no estoque MySQL.")
        for id_reserva, id_lote, status, quantidade in registros:
            if status not in {"ativa", "separada"} and not (entrega and status == "cortada"):
                raise ErroEstoque("A reserva MySQL já foi cortada ou encerrada.")
            cursor.execute(
                "UPDATE reserva SET status = %s WHERE id_reserva = %s",
                ["consumida" if entrega else "liberada", id_reserva],
            )
            if entrega:
                cursor.execute(
                    "INSERT INTO movimentacao (id_estoque, id_reserva, id_usuario, tipo, quantidade) "
                    "VALUES (%s, %s, %s, 'entrega', %s)",
                    [id_lote, id_reserva, id_usuario, 0 if status == "cortada" else -quantidade],
                )


def atualizar_pedido(pedido, status):
    if pedido.mysql_pedido_id is not None:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE pedido SET status = %s WHERE id_pedido = %s", [status, pedido.mysql_pedido_id])
