"""Testes das regras do módulo 4 contra o banco MySQL REAL do projeto.

Cada teste recria a base descartável ``estoque_vidracaria_teste`` com os scripts do
repositório (banco/mysql/sql), então os gatilhos e restrições testados são os do
banco do grupo. A base de demonstração ``_v2`` não é tocada.

    python manage.py test movimentacoes

Precisa de um usuário MySQL que possa criar bancos (MYSQL_USER / MYSQL_PASSWORD).
"""
import unittest
from datetime import date
from decimal import Decimal

from movimentacoes import services as em

from .base import BANCO_TESTE, pular_sem_mysql, preparar_banco


@pular_sem_mysql
class BaseTeste(unittest.TestCase):
    """Cada teste começa com a demonstração do repositório recém-carregada.

    Demonstração: lote 1 = chapas 2000x1000 (físico 2, reservado 1, disponível 1);
    lote 2 = perfil em metros (25,5); lote 3 = sobra 800x500 (1).
    """

    def setUp(self):
        preparar_banco()  # base nova a cada teste: nenhum teste depende do anterior
        self.conn = em.conectar(database=BANCO_TESTE)
        with self.conn.cursor() as cur:
            cur.execute("SELECT login, id_usuario FROM usuario")
            ids = {r["login"]: r["id_usuario"] for r in cur.fetchall()}
        self.conn.commit()
        self.estoque, self.producao = ids["demo.estoque"], ids["demo.producao"]
        self.admin, self.vendas = ids["teste.admin"], ids["teste.vendas"]
        self.snapshot = self._estado()

    def tearDown(self):
        self.conn.close()

    def _estado(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id_estoque, saldo_fisico FROM estoque WHERE id_estoque <= 3")
            fisicos = {r["id_estoque"]: r["saldo_fisico"] for r in cur.fetchall()}
            cur.execute("SELECT COALESCE(MAX(id_movimentacao), 0) AS m FROM movimentacao")
            max_mov = cur.fetchone()["m"]
            cur.execute("SELECT COUNT(*) AS n FROM estoque")
            lotes = cur.fetchone()["n"]
        self.conn.commit()
        return {"fisicos": fisicos, "max_mov": max_mov, "lotes": lotes}

    def assertNadaMudou(self):
        self.assertEqual(self._estado(), self.snapshot)

    def saldo(self, id_estoque):
        return next(l for l in em.listar_lotes(self.conn) if l["id_estoque"] == id_estoque)


class TesteEntradas(BaseTeste):
    def test_entrada_em_lote_existente_soma_saldo_e_grava_historico(self):
        r = em.registrar_entrada(self.conn, id_usuario=self.estoque, id_estoque=1,
                                 quantidade=2, nota_fiscal="NF-100")
        self.assertEqual(r["saldo_fisico"], Decimal("4"))
        mov = em.listar_movimentacoes(self.conn, tipos=("entrada",), id_estoque=1)[0]
        self.assertEqual((mov["nota_fiscal"], mov["quantidade"], mov["responsavel"]),
                         ("NF-100", Decimal("2"), "Operador de estoque"))
        self.assertEqual(mov["area_m2"], Decimal("4"))  # 2 chapas de 2 m²

    def test_entrada_cria_lote_novo_e_depois_reaproveita_o_identico(self):
        dados = dict(id_usuario=self.estoque, id_material=1, localizacao="Galpão C", id_fornecedor=1,
                     largura_mm=3210, altura_mm=2250, custo_unitario="210,50", nota_fiscal="NF-200")
        primeira = em.registrar_entrada(self.conn, quantidade=4, **dados)
        segunda = em.registrar_entrada(self.conn, quantidade=1, **dados)
        self.assertTrue(primeira["lote_novo"])
        self.assertFalse(segunda["lote_novo"])
        self.assertEqual(primeira["id_estoque"], segunda["id_estoque"])
        self.assertEqual(segunda["saldo_fisico"], Decimal("5"))

    def test_entrada_em_metros_aceita_decimal(self):
        r = em.registrar_entrada(self.conn, id_usuario=self.estoque, id_estoque=2,
                                 quantidade="10,5", nota_fiscal="NF-300")
        self.assertEqual(r["saldo_fisico"], Decimal("36"))

    def test_entrada_recusa_dados_invalidos_e_nao_grava_nada(self):
        base = dict(id_usuario=self.estoque, id_estoque=1, quantidade=1, nota_fiscal="NF-1")
        casos = {
            "sem nota fiscal": dict(base, nota_fiscal="  "),
            "quantidade zero": dict(base, quantidade=0),
            "quantidade negativa": dict(base, quantidade=-3),
            "chapa fracionada": dict(base, quantidade="1,5"),
            "texto no lugar de número": dict(base, quantidade="abc"),
            "sobra não recebe entrada": dict(base, id_estoque=3),
            "lote inexistente": dict(base, id_estoque=999),
            "perfil sem permissão": dict(base, id_usuario=self.vendas),
            "usuário inexistente": dict(base, id_usuario=999),
        }
        for nome, args in casos.items():
            with self.subTest(nome), self.assertRaises(em.EstoqueError):
                em.registrar_entrada(self.conn, **args)
        novo = dict(id_usuario=self.estoque, id_material=1, quantidade=1, nota_fiscal="NF-2",
                    localizacao="Galpão C", largura_mm=1000, altura_mm=1000)
        casos_novo = {
            "chapa sem medidas": dict(novo, largura_mm=None, altura_mm=None),
            "só a largura": dict(novo, altura_mm=None),
            "medida negativa": dict(novo, largura_mm=-5),
            "sem localização": dict(novo, localizacao=""),
            "custo negativo": dict(novo, custo_unitario=-1),
            "fornecedor inexistente": dict(novo, id_fornecedor=999),
            "material inexistente": dict(novo, id_material=999),
        }
        for nome, args in casos_novo.items():
            with self.subTest(nome), self.assertRaises(em.EstoqueError):
                em.registrar_entrada(self.conn, **args)
        self.assertNadaMudou()  # nem saldo, nem histórico, nem lote criado pela metade


class TestePerdas(BaseTeste):
    def test_perda_baixa_o_estoque_e_registra_motivo_e_responsavel(self):
        r = em.registrar_perda(self.conn, id_estoque=1, quantidade=1, categoria="Quebra",
                               motivo="Caiu na descarga", id_usuario=self.producao)
        self.assertEqual((r["saldo_fisico"], r["disponivel"]), (Decimal("1"), Decimal("0")))
        mov = em.listar_movimentacoes(self.conn, tipos=("perda",))[0]
        self.assertEqual(mov["quantidade"], Decimal("-1"))
        self.assertEqual(mov["motivo"], "Quebra: Caiu na descarga")
        self.assertEqual(mov["responsavel"], "Operador de produção")

    def test_nao_perde_material_reservado(self):
        with self.assertRaises(em.EstoqueError) as ctx:
            em.registrar_perda(self.conn, id_estoque=1, quantidade=2, categoria="quebra",
                               motivo="x", id_usuario=self.estoque)
        self.assertIn("reservado", str(ctx.exception))
        self.assertNadaMudou()

    def test_perda_maior_que_o_estoque(self):
        with self.assertRaises(em.EstoqueError):
            em.registrar_perda(self.conn, id_estoque=2, quantidade=100, categoria="defeito",
                               motivo="lote com defeito", id_usuario=self.estoque)
        self.assertNadaMudou()

    def test_perda_em_metros_aceita_fracao(self):
        r = em.registrar_perda(self.conn, id_estoque=2, quantidade="0,5", categoria="defeito",
                               motivo="Barra torta", id_usuario=self.estoque)
        self.assertEqual(r["saldo_fisico"], Decimal("25"))

    def test_perda_recusa_dados_invalidos(self):
        base = dict(id_estoque=1, quantidade=1, categoria="quebra", motivo="ok", id_usuario=self.estoque)
        casos = {
            "sem motivo": dict(base, motivo=" "),
            "categoria inválida": dict(base, categoria="roubo"),
            "chapa fracionada": dict(base, quantidade="0,5"),
            "quantidade zero": dict(base, quantidade=0),
            "vendas não registra perda": dict(base, id_usuario=self.vendas),
            "motivo gigante": dict(base, motivo="x" * 300),
        }
        for nome, args in casos.items():
            with self.subTest(nome), self.assertRaises(em.EstoqueError):
                em.registrar_perda(self.conn, **args)
        self.assertNadaMudou()


class TesteAjustes(BaseTeste):
    def test_ajuste_para_baixo_e_para_cima(self):
        r = em.registrar_ajuste(self.conn, id_estoque=1, quantidade_contada=1,
                                justificativa="Contagem mensal", id_usuario=self.admin)
        self.assertEqual((r["diferenca"], r["saldo_fisico"]), (Decimal("-1"), Decimal("1")))
        r = em.registrar_ajuste(self.conn, id_estoque=1, quantidade_contada=4,
                                justificativa="Chapa achada no fundo", id_usuario=self.admin)
        self.assertEqual((r["diferenca"], r["saldo_fisico"]), (Decimal("3"), Decimal("4")))
        mov = em.listar_movimentacoes(self.conn, tipos=("ajuste",))[0]
        self.assertEqual(mov["motivo"], "Chapa achada no fundo (sistema: 1, contado: 4)")

    def test_so_administracao_autoriza(self):
        for usuario in (self.estoque, self.producao, self.vendas):
            with self.subTest(usuario), self.assertRaises(em.EstoqueError):
                em.registrar_ajuste(self.conn, id_estoque=1, quantidade_contada=1,
                                    justificativa="x", id_usuario=usuario)
        self.assertNadaMudou()

    def test_ajuste_recusa_casos_invalidos(self):
        base = dict(id_estoque=1, quantidade_contada=1, justificativa="ok", id_usuario=self.admin)
        casos = {
            "sem justificativa": dict(base, justificativa=""),
            "contagem igual ao sistema": dict(base, quantidade_contada=2),
            "abaixo do reservado": dict(base, quantidade_contada=0),
            "contagem negativa": dict(base, quantidade_contada=-1),
            "chapa fracionada": dict(base, quantidade_contada="1,5"),
            "justificativa gigante": dict(base, justificativa="x" * 199),
        }
        for nome, args in casos.items():
            with self.subTest(nome), self.assertRaises(em.EstoqueError):
                em.registrar_ajuste(self.conn, **args)
        self.assertNadaMudou()


class TesteConsultas(BaseTeste):
    def test_historico_filtra_por_tipo_e_data(self):
        em.registrar_perda(self.conn, id_estoque=2, quantidade=1, categoria="extravio",
                           motivo="Sumiu do galpão", id_usuario=self.estoque)
        perdas = em.listar_movimentacoes(self.conn, tipos=("perda",))
        self.assertEqual([m["tipo"] for m in perdas], ["perda"])
        hoje = date.today()
        self.assertTrue(em.listar_movimentacoes(self.conn, data_inicio=hoje, data_fim=hoje))
        self.assertFalse(em.listar_movimentacoes(self.conn, data_fim=date(2000, 1, 1)))
        tudo = {m["tipo"] for m in em.listar_movimentacoes(self.conn)}
        self.assertTrue(tudo <= {"entrada", "perda", "ajuste"})  # corte/entrega ficam fora

    def test_resumo_de_perdas_por_categoria(self):
        em.registrar_perda(self.conn, id_estoque=2, quantidade=2, categoria="defeito",
                           motivo="Barra torta", id_usuario=self.estoque)
        resumo = em.resumo_perdas(self.conn)
        linha = next(r for r in resumo if r["codigo"] == "PER-01")
        self.assertEqual((linha["categoria"], linha["quantidade"], linha["custo_estimado"]),
                         ("defeito", Decimal("2"), Decimal("33.00")))  # 2 m x R$ 16,50


class TesteBanco(BaseTeste):
    def test_banco_continua_recusando_sozinho(self):
        """As travas do banco valem mesmo se alguém pular as validações do módulo."""
        with self.assertRaises(em.EstoqueError):
            with em.transacao(self.conn) as cur:
                em._gravar_movimentacao(cur, 1, self.estoque, "perda", Decimal("-2"), motivo="forçado")
        self.assertNadaMudou()


if __name__ == "__main__":
    unittest.main()
