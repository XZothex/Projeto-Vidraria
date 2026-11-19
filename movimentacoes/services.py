"""Módulo 4 - Entradas, perdas e ajustes de estoque (MySQL ``estoque_vidracaria_v2``).

Como este módulo conversa com o banco do grupo (banco/mysql/sql/create_tables.sql):

* O estoque é por LOTE (tabela ``estoque``): cada recebimento de chapa, ou cada
  sobra, tem suas medidas, localização, fornecedor e custo.
* O saldo NUNCA é alterado diretamente. Toda mudança é um INSERT em
  ``movimentacao``; os gatilhos do banco somam o valor em ``estoque.saldo_fisico``.
  Aqui só gravamos: entrada (+), perda (-) e ajuste (+/-).
* O banco já recusa saldo negativo, saldo físico abaixo do reservado, perda/ajuste
  sem motivo e sinais errados. Este módulo valida ANTES, para mostrar mensagens
  claras ao usuário, e trava o lote (SELECT ... FOR UPDATE) para duas pessoas não
  mexerem no mesmo lote ao mesmo tempo.
* O LEIA-ME do banco diz que a aplicação deve validar as regras por unidade:
  chapa/peça só aceitam quantidade inteira; metro e m² aceitam até 3 casas.

Configuração da conexão (variáveis de ambiente; o ``config/settings.py`` já carrega o .env):
MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE.
Dependência: ``pip install pymysql`` (está no requirements.txt).
"""
import os
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import MySQLError

# Quem pode fazer o quê (perfis da tabela ``usuario``). Ajustar aqui se o grupo
# ou o cliente decidirem diferente; o módulo de login pode substituir isto.
PERFIS_ENTRADA = {"administracao", "estoque"}
PERFIS_PERDA = {"administracao", "estoque", "producao"}
PERFIS_AJUSTE = {"administracao"}  # o cliente pediu que ajustes sejam autorizados

CATEGORIAS_PERDA = ("quebra", "defeito", "extravio")
UNIDADES_INTEIRAS = {"chapa", "peca"}
TIPOS_DESTE_MODULO = ("entrada", "perda", "ajuste")
TIPOS_HISTORICO = {
    "entrada": "Entrada", "perda": "Perda", "ajuste": "Ajuste",
    "corte": "Corte", "sobra": "Sobra", "entrega": "Entrega", "devolucao": "Devolução",
}


class EstoqueError(Exception):
    """Operação recusada por uma regra de negócio (mensagem pronta para o usuário)."""


# --------------------------------------------------------------- conexão

def conectar(database=None):
    """Abre a conexão. As transações são controladas por ``transacao()``."""
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=database or os.environ.get("MYSQL_DATABASE", "estoque_vidracaria_v2"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def conexao(database=None):
    """Abre a conexão e garante que ela seja fechada ao sair do ``with``."""
    conn = conectar(database)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transacao(conn):
    """Abre uma transação: confirma se tudo der certo, desfaz se qualquer coisa falhar.

    Erros do banco que representam regra de negócio (CHECK, gatilhos) viram
    ``EstoqueError``; qualquer outro erro continua sendo levantado normalmente.
    """
    conn.begin()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except EstoqueError:
        conn.rollback()
        raise
    except MySQLError as erro:
        conn.rollback()
        codigo = erro.args[0] if erro.args else None
        mensagem = erro.args[1] if len(erro.args) > 1 else str(erro)
        if codigo == 1644:  # SIGNAL dos gatilhos: a mensagem já está em português
            raise EstoqueError(mensagem) from erro
        if codigo in (3819, 4025):  # CHECK violado
            raise EstoqueError(
                "O banco recusou a operação: o saldo ficaria inválido "
                "(negativo ou abaixo do que está reservado)."
            ) from erro
        if codigo == 1452:  # chave estrangeira
            raise EstoqueError("Registro relacionado não encontrado (material, lote, fornecedor ou usuário).") from erro
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


# ------------------------------------------------------------ validações

def mm_para_m2(largura_mm, altura_mm, quantidade=1):
    """Converte medidas em mm para m² (2000 x 1000 mm = 2 m²)."""
    if not largura_mm or not altura_mm:
        return None
    return Decimal(largura_mm) * Decimal(altura_mm) * Decimal(quantidade) / Decimal(1_000_000)


def _fmt(valor):
    return f"{Decimal(valor).normalize():f}"


formatar_quantidade = _fmt  # versão pública, usada pelas telas


def _decimal(valor, campo, casas):
    if isinstance(valor, bool) or valor is None:
        raise EstoqueError(f"{campo} é obrigatório.")
    try:
        numero = Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        raise EstoqueError(f"{campo} inválido.") from None
    if not numero.is_finite():
        raise EstoqueError(f"{campo} inválido.")
    if numero.as_tuple().exponent < -casas:
        raise EstoqueError(f"{campo} aceita no máximo {casas} casa(s) decimal(is).")
    return numero


def _quantidade(valor, unidade, campo="Quantidade", permitir_zero=False):
    qtd = _decimal(valor, campo, 3)
    if qtd < 0 or (qtd == 0 and not permitir_zero):
        raise EstoqueError(f"{campo} deve ser maior que zero.")
    if qtd >= Decimal("1000000000"):
        raise EstoqueError(f"{campo} muito grande.")
    if unidade in UNIDADES_INTEIRAS and qtd != qtd.to_integral_value():
        raise EstoqueError(f"{campo} deve ser um número inteiro para material controlado em {unidade}.")
    return qtd


def _texto(valor, campo, maximo, obrigatorio=True):
    texto = (valor or "").strip()
    if obrigatorio and not texto:
        raise EstoqueError(f"{campo} é obrigatório.")
    if len(texto) > maximo:
        raise EstoqueError(f"{campo} pode ter no máximo {maximo} caracteres.")
    return texto or None


def _medida(valor, campo):
    if valor in (None, ""):
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise EstoqueError(f"{campo} inválida (use milímetros, número inteiro).") from None
    if numero <= 0:
        raise EstoqueError(f"{campo} deve ser maior que zero.")
    return numero


def _usuario(cur, id_usuario, perfis_permitidos, acao):
    cur.execute("SELECT id_usuario, nome, perfil FROM usuario WHERE id_usuario = %s", (id_usuario,))
    usuario = cur.fetchone()
    if usuario is None:
        raise EstoqueError("Usuário responsável não encontrado.")
    if usuario["perfil"] not in perfis_permitidos:
        raise EstoqueError(f"Seu perfil não tem permissão para {acao}.")
    return usuario


def _lote_travado(cur, id_estoque):
    """Lote com trava (FOR UPDATE), junto com os dados do material."""
    cur.execute(
        """SELECT e.*, m.codigo, m.descricao, m.unidade
           FROM estoque e JOIN material m ON m.id_material = e.id_material
           WHERE e.id_estoque = %s FOR UPDATE""",
        (id_estoque,),
    )
    lote = cur.fetchone()
    if lote is None:
        raise EstoqueError("Lote de estoque não encontrado.")
    return lote


def _gravar_movimentacao(cur, id_estoque, id_usuario, tipo, quantidade, nota_fiscal=None, motivo=None):
    """Único ponto que escreve em ``movimentacao`` (o gatilho atualiza o saldo)."""
    cur.execute(
        """INSERT INTO movimentacao (id_estoque, id_usuario, tipo, quantidade, nota_fiscal, motivo)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (id_estoque, id_usuario, tipo, quantidade, nota_fiscal, motivo),
    )
    return cur.lastrowid


def _saldo(cur, id_estoque):
    cur.execute(
        "SELECT saldo_fisico, saldo_reservado, saldo_fisico - saldo_reservado AS disponivel "
        "FROM estoque WHERE id_estoque = %s",
        (id_estoque,),
    )
    return cur.fetchone()


# ------------------------------------------------------------- operações

def registrar_entrada(conn, *, id_usuario, quantidade, nota_fiscal, id_estoque=None,
                      id_material=None, localizacao=None, id_fornecedor=None,
                      largura_mm=None, altura_mm=None, custo_unitario=None, motivo=None):
    """Recebimento de material (compra), com número da nota fiscal conferida.

    Duas formas de usar:
    * ``id_estoque=...``: soma em um lote de compra que já existe.
    * ``id_material=...`` + ``localizacao`` (+ medidas, fornecedor, custo): se já existir
      um lote de compra idêntico (mesmo material, fornecedor, medidas, localização e
      custo) a quantidade entra nele; senão um lote novo é criado.

    Chapas exigem largura e altura em mm. Retorna um dicionário com os ids e o saldo.
    """
    nota_fiscal = _texto(nota_fiscal, "Número da nota fiscal", 60)
    motivo = _texto(motivo, "Motivo", 200, obrigatorio=False)

    with transacao(conn) as cur:
        _usuario(cur, id_usuario, PERFIS_ENTRADA, "registrar entradas")
        lote_novo = False

        if id_estoque is not None:
            lote = _lote_travado(cur, id_estoque)
            if lote["origem"] != "compra":
                raise EstoqueError("Sobras entram pelo módulo de cortes, não por recebimento.")
            unidade = lote["unidade"]
        else:
            if id_material is None:
                raise EstoqueError("Informe o lote (id_estoque) ou o material (id_material).")
            cur.execute("SELECT id_material, unidade FROM material WHERE id_material = %s", (id_material,))
            material = cur.fetchone()
            if material is None:
                raise EstoqueError("Material não encontrado.")
            unidade = material["unidade"]

            localizacao = _texto(localizacao, "Localização no estoque", 100)
            largura_mm, altura_mm = _medida(largura_mm, "Largura"), _medida(altura_mm, "Altura")
            if (largura_mm is None) != (altura_mm is None):
                raise EstoqueError("Informe largura e altura juntas (ou nenhuma das duas).")
            if unidade == "chapa" and largura_mm is None:
                raise EstoqueError("Chapas exigem largura e altura em milímetros.")
            if custo_unitario is not None:
                custo_unitario = _decimal(custo_unitario, "Custo", 2)
                if custo_unitario < 0:
                    raise EstoqueError("Custo não pode ser negativo.")
            if id_fornecedor is not None:
                cur.execute("SELECT 1 FROM fornecedor WHERE id_fornecedor = %s", (id_fornecedor,))
                if cur.fetchone() is None:
                    raise EstoqueError("Fornecedor não encontrado.")

            cur.execute(  # <=> compara também NULL com NULL
                """SELECT id_estoque FROM estoque
                   WHERE id_material = %s AND origem = 'compra' AND localizacao = %s
                     AND id_fornecedor <=> %s AND largura_mm <=> %s AND altura_mm <=> %s
                     AND custo_unitario <=> %s
                   ORDER BY id_estoque LIMIT 1 FOR UPDATE""",
                (id_material, localizacao, id_fornecedor, largura_mm, altura_mm, custo_unitario),
            )
            existente = cur.fetchone()
            if existente:
                id_estoque = existente["id_estoque"]
            else:
                cur.execute(
                    """INSERT INTO estoque (id_material, id_fornecedor, localizacao, origem,
                                            largura_mm, altura_mm, custo_unitario)
                       VALUES (%s, %s, %s, 'compra', %s, %s, %s)""",
                    (id_material, id_fornecedor, localizacao, largura_mm, altura_mm, custo_unitario),
                )
                id_estoque = cur.lastrowid
                lote_novo = True

        qtd = _quantidade(quantidade, unidade)
        id_mov = _gravar_movimentacao(cur, id_estoque, id_usuario, "entrada", qtd, nota_fiscal, motivo)
        saldo = _saldo(cur, id_estoque)

    return {"id_movimentacao": id_mov, "id_estoque": id_estoque, "lote_novo": lote_novo,
            "saldo_fisico": saldo["saldo_fisico"], "disponivel": saldo["disponivel"]}


def registrar_perda(conn, *, id_estoque, quantidade, categoria, motivo, id_usuario):
    """Quebra, defeito ou extravio de material de um lote.

    O banco não tem coluna de categoria, então ela vai no início do motivo
    ("Quebra: caiu na descarga"). Só dá para dar baixa no que está DISPONÍVEL
    (físico menos reservado): material reservado para pedido não pode ser perdido
    sem antes liberar a reserva.
    """
    categoria = (categoria or "").strip().lower()
    if categoria not in CATEGORIAS_PERDA:
        raise EstoqueError(f"Tipo de perda inválido. Use: {', '.join(CATEGORIAS_PERDA)}.")
    motivo = _texto(motivo, "Motivo da perda", 200 - len(categoria) - 2)
    motivo_final = f"{categoria.capitalize()}: {motivo}"

    with transacao(conn) as cur:
        _usuario(cur, id_usuario, PERFIS_PERDA, "registrar perdas")
        lote = _lote_travado(cur, id_estoque)
        qtd = _quantidade(quantidade, lote["unidade"])
        disponivel = lote["saldo_fisico"] - lote["saldo_reservado"]
        if qtd > lote["saldo_fisico"]:
            raise EstoqueError(f"Este lote tem apenas {_fmt(lote['saldo_fisico'])} em estoque.")
        if qtd > disponivel:
            raise EstoqueError(
                f"Só {_fmt(disponivel)} está disponível: {_fmt(lote['saldo_reservado'])} "
                "está reservado para pedidos. Libere a reserva antes de registrar a perda."
            )
        id_mov = _gravar_movimentacao(cur, id_estoque, id_usuario, "perda", -qtd, motivo=motivo_final)
        saldo = _saldo(cur, id_estoque)

    return {"id_movimentacao": id_mov, "id_estoque": id_estoque,
            "saldo_fisico": saldo["saldo_fisico"], "disponivel": saldo["disponivel"]}


def registrar_ajuste(conn, *, id_estoque, quantidade_contada, justificativa, id_usuario):
    """Ajuste de inventário: iguala o sistema à contagem física do lote.

    Só o perfil ``administracao`` autoriza. A justificativa é obrigatória e o
    motivo gravado inclui o saldo do sistema e o contado, para o histórico.
    """
    justificativa = _texto(justificativa, "Justificativa do ajuste", 200)

    with transacao(conn) as cur:
        _usuario(cur, id_usuario, PERFIS_AJUSTE, "autorizar ajustes de estoque")
        lote = _lote_travado(cur, id_estoque)
        contada = _quantidade(quantidade_contada, lote["unidade"], "Quantidade contada", permitir_zero=True)
        fisico, reservado = lote["saldo_fisico"], lote["saldo_reservado"]
        delta = contada - fisico
        if delta == 0:
            raise EstoqueError("A contagem é igual ao saldo do sistema; não há o que ajustar.")
        if contada < reservado:
            raise EstoqueError(
                f"A contagem ({_fmt(contada)}) é menor que o reservado para pedidos "
                f"({_fmt(reservado)}). Corrija ou libere as reservas antes de ajustar."
            )
        motivo = f"{justificativa} (sistema: {_fmt(fisico)}, contado: {_fmt(contada)})"
        if len(motivo) > 200:
            raise EstoqueError(f"Justificativa muito longa: use até {200 - len(motivo) + len(justificativa)} caracteres.")
        id_mov = _gravar_movimentacao(cur, id_estoque, id_usuario, "ajuste", delta, motivo=motivo)
        saldo = _saldo(cur, id_estoque)

    return {"id_movimentacao": id_mov, "id_estoque": id_estoque, "diferenca": delta,
            "saldo_fisico": saldo["saldo_fisico"], "disponivel": saldo["disponivel"]}


# -------------------------------------------------------------- consultas

def listar_lotes(conn, id_material=None, somente_com_saldo=False):
    """Lotes com saldo físico, reservado e disponível (view ``saldo_estoque``)."""
    sql, params = "SELECT * FROM saldo_estoque WHERE 1=1", []
    if id_material is not None:
        sql += " AND id_material = %s"
        params.append(id_material)
    if somente_com_saldo:
        sql += " AND fisico > 0"
    with conn.cursor() as cur:
        cur.execute(sql + " ORDER BY id_estoque", params)
        resultado = cur.fetchall()
    conn.commit()  # encerra a leitura (não deixa transação aberta)
    return resultado


def listar_movimentacoes(conn, tipos=TIPOS_DESTE_MODULO, id_material=None, id_estoque=None,
                         data_inicio=None, data_fim=None, limite=500):
    """Histórico de movimentações, do mais recente ao mais antigo.

    ``data_inicio`` e ``data_fim`` são ``datetime.date`` (fim inclusivo).
    ``area_m2`` é a área movimentada (medidas do lote x quantidade), quando há medidas.
    """
    tipos = [t for t in tipos if t in TIPOS_HISTORICO] or list(TIPOS_DESTE_MODULO)
    sql = f"""SELECT mov.id_movimentacao, mov.data_movimentacao, mov.tipo, mov.quantidade,
                     mov.nota_fiscal, mov.motivo, mov.id_estoque, e.localizacao,
                     e.largura_mm, e.altura_mm, e.custo_unitario,
                     m.id_material, m.codigo, m.descricao, m.unidade,
                     f.razao_social AS fornecedor, u.nome AS responsavel,
                     CASE WHEN m.unidade IN ('chapa', 'peca') AND e.largura_mm IS NOT NULL
                          THEN ABS(mov.quantidade) * e.largura_mm * e.altura_mm / 1000000
                     END AS area_m2
              FROM movimentacao mov
              JOIN estoque e ON e.id_estoque = mov.id_estoque
              JOIN material m ON m.id_material = e.id_material
              JOIN usuario u ON u.id_usuario = mov.id_usuario
              LEFT JOIN fornecedor f ON f.id_fornecedor = e.id_fornecedor
              WHERE mov.tipo IN ({', '.join(['%s'] * len(tipos))})"""
    params = list(tipos)
    if id_material is not None:
        sql += " AND m.id_material = %s"
        params.append(id_material)
    if id_estoque is not None:
        sql += " AND mov.id_estoque = %s"
        params.append(id_estoque)
    if data_inicio is not None:
        sql += " AND mov.data_movimentacao >= %s"
        params.append(data_inicio)
    if data_fim is not None:
        sql += " AND mov.data_movimentacao < %s"
        params.append(data_fim + timedelta(days=1))
    sql += " ORDER BY mov.data_movimentacao DESC, mov.id_movimentacao DESC LIMIT %s"
    params.append(int(limite))
    with conn.cursor() as cur:
        cur.execute(sql, params)
        resultado = cur.fetchall()
    conn.commit()
    return resultado


def resumo_perdas(conn, data_inicio=None, data_fim=None):
    """Perdas por material e categoria, com quantidade e custo estimado.

    Serve para o cliente acompanhar as perdas e descobrir as causas (quebra,
    defeito, extravio).
    """
    sql = """SELECT m.codigo, m.descricao, m.unidade,
                    LOWER(SUBSTRING_INDEX(mov.motivo, ':', 1)) AS categoria,
                    COUNT(*) AS ocorrencias,
                    -SUM(mov.quantidade) AS quantidade,
                    -SUM(mov.quantidade * COALESCE(e.custo_unitario, 0)) AS custo_estimado
             FROM movimentacao mov
             JOIN estoque e ON e.id_estoque = mov.id_estoque
             JOIN material m ON m.id_material = e.id_material
             WHERE mov.tipo = 'perda'"""
    params = []
    if data_inicio is not None:
        sql += " AND mov.data_movimentacao >= %s"
        params.append(data_inicio)
    if data_fim is not None:
        sql += " AND mov.data_movimentacao < %s"
        params.append(data_fim + timedelta(days=1))
    sql += " GROUP BY m.id_material, m.codigo, m.descricao, m.unidade, categoria ORDER BY custo_estimado DESC"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        resultado = cur.fetchall()
    conn.commit()
    return resultado


def _consultar(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        resultado = cur.fetchall()
    conn.commit()
    return resultado


def listar_materiais(conn):
    """Materiais cadastrados (para os campos de seleção dos formulários)."""
    return _consultar(conn, "SELECT id_material, codigo, descricao, unidade FROM material ORDER BY codigo")


def listar_fornecedores(conn):
    return _consultar(conn, "SELECT id_fornecedor, razao_social FROM fornecedor ORDER BY razao_social")


def buscar_usuario_por_login(conn, login):
    """Usuário da tabela ``usuario`` (id e perfil) a partir do login do Django."""
    linhas = _consultar(conn, "SELECT id_usuario, nome, login, perfil FROM usuario WHERE login = %s", (login,))
    return linhas[0] if linhas else None
