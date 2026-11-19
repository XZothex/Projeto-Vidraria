"""Apoio dos testes: base MySQL descartável criada a partir dos scripts do repositório.

Se não houver MySQL acessível (variáveis MYSQL_* no .env), os testes deste app são
PULADOS, para não atrapalhar quem roda ``manage.py test`` sem o banco.
"""
import os
import unittest
from pathlib import Path
from unittest import mock

from django.conf import settings

from movimentacoes import services as em

BANCO_TESTE = "estoque_vidracaria_teste"
SQL_DIR = Path(settings.BASE_DIR) / "banco" / "mysql" / "sql"


def executar_script(conn, texto):
    """Executa um script SQL respeitando ``DELIMITER`` (que é comando do cliente mysql)."""
    delimitador, bloco = ";", []
    with conn.cursor() as cur:
        for linha in texto.splitlines():
            limpa = linha.strip()
            if limpa.upper().startswith("DELIMITER"):
                delimitador = limpa.split()[1]
                continue
            if not limpa or limpa.startswith("--"):
                continue
            bloco.append(linha)
            if limpa.endswith(delimitador):
                comando = "\n".join(bloco).rstrip()
                cur.execute(comando[: -len(delimitador)])
                bloco = []
    conn.commit()


def preparar_banco():
    admin = em.conectar(database="mysql")
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {BANCO_TESTE}")
    admin.commit()
    for nome in ("create_tables.sql", "inserts.sql"):
        texto = (SQL_DIR / nome).read_text(encoding="utf-8").replace("estoque_vidracaria_v2", BANCO_TESTE)
        executar_script(admin, texto)
    with admin.cursor() as cur:
        cur.execute(f"USE {BANCO_TESTE}")
        cur.execute("INSERT INTO usuario (nome, login, perfil) VALUES "
                    "('Gerente', 'teste.admin', 'administracao'), ('Vendedor', 'teste.vendas', 'vendas')")
    admin.commit()
    admin.close()




def mysql_disponivel():
    try:
        em.conectar(database="mysql").close()
        return True
    except Exception:
        return False


def pular_sem_mysql(cls):
    return unittest.skipUnless(mysql_disponivel(), "MySQL indisponível: configure MYSQL_* no .env")(cls)


def usar_base_de_teste():
    """Faz ``conectar()`` sem argumento apontar para a base de teste."""
    patcher = mock.patch.dict(os.environ, {"MYSQL_DATABASE": BANCO_TESTE})
    patcher.start()
    return patcher
