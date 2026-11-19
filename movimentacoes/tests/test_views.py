"""Testes das telas do app movimentacoes (cliente de teste do Django + MySQL de teste).

O usuário do Django é ligado à tabela ``usuario`` do banco pelo login
(``username`` == ``usuario.login``). Sem MySQL configurado, estes testes são pulados.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .base import preparar_banco, pular_sem_mysql, usar_base_de_teste


@pular_sem_mysql
class BaseViewTest(TestCase):
    """Demonstração do repositório: lote 1 = chapas 2000x1000 (físico 2, reservado 1)."""

    def setUp(self):
        preparar_banco()
        patcher = usar_base_de_teste()
        self.addCleanup(patcher.stop)
        User = get_user_model()
        # logins iguais aos de usuario.login no banco de teste
        for login in ("demo.estoque", "demo.producao", "teste.admin", "teste.vendas", "sem.cadastro"):
            User.objects.create_user(login, password="senha-teste-123")

    def entrar(self, login):
        self.client.force_login(get_user_model().objects.get(username=login))


class TesteAcesso(BaseViewTest):
    URLS = ["movimentacoes:lotes", "movimentacoes:historico", "movimentacoes:entrada",
            "movimentacoes:perda", "movimentacoes:ajuste"]

    def test_exige_login(self):
        for nome in self.URLS:
            with self.subTest(nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 302)
                self.assertIn("/entrar/", resposta["Location"])

    def test_usuario_sem_cadastro_no_banco_de_estoque(self):
        self.entrar("sem.cadastro")
        resposta = self.client.get(reverse("movimentacoes:lotes"))
        self.assertContains(resposta, "não está cadastrado", status_code=403)

    def test_permissoes_por_perfil(self):
        esperado = {  # login: (entrada, perda, ajuste)
            "demo.estoque": (200, 200, 403),
            "demo.producao": (403, 200, 403),
            "teste.vendas": (403, 403, 403),
            "teste.admin": (200, 200, 200),
        }
        for login, (entrada, perda, ajuste) in esperado.items():
            self.entrar(login)
            with self.subTest(login):
                self.assertEqual(self.client.get(reverse("movimentacoes:entrada")).status_code, entrada)
                self.assertEqual(self.client.get(reverse("movimentacoes:perda")).status_code, perda)
                self.assertEqual(self.client.get(reverse("movimentacoes:ajuste")).status_code, ajuste)

    def test_botoes_so_aparecem_para_quem_pode(self):
        self.entrar("teste.vendas")
        resposta = self.client.get(reverse("movimentacoes:lotes"))
        self.assertContains(resposta, "VID-T8")
        for texto in ("Registrar entrada", "Registrar perda", "Ajuste de inventário"):
            self.assertNotContains(resposta, texto)
        self.entrar("teste.admin")
        resposta = self.client.get(reverse("movimentacoes:lotes"))
        for texto in ("Registrar entrada", "Registrar perda", "Ajuste de inventário"):
            self.assertContains(resposta, texto)

    def test_mensagem_quando_o_banco_esta_fora(self):
        from unittest import mock

        from pymysql.err import OperationalError
        self.entrar("teste.admin")
        with mock.patch("movimentacoes.services.pymysql.connect", side_effect=OperationalError(2003, "x")):
            resposta = self.client.get(reverse("movimentacoes:lotes"))
        self.assertContains(resposta, "conectar ao banco", status_code=503)


class TesteEntrada(BaseViewTest):
    def setUp(self):
        super().setUp()
        self.entrar("demo.estoque")
        self.url = reverse("movimentacoes:entrada")

    def test_formulario_lista_lotes_materiais_e_fornecedores(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "#1 VID-T8")
        self.assertContains(resposta, "PER-01")
        self.assertContains(resposta, "Vidros Brasil")
        self.assertNotContains(resposta, "[sobra]")  # sobra não recebe entrada

    def test_entrada_em_lote_existente(self):
        resposta = self.client.post(self.url, {"id_estoque": "1", "quantidade": "2", "nota_fiscal": "NF-9"}, follow=True)
        self.assertContains(resposta, "Entrada registrada no lote existente")
        self.assertContains(resposta, "NF-9")  # aparece no histórico

    def test_entrada_cria_lote_novo(self):
        resposta = self.client.post(self.url, {
            "id_material": "1", "localizacao": "Galpão C", "id_fornecedor": "1", "largura_mm": "3210",
            "altura_mm": "2250", "custo_unitario": "210,50", "quantidade": "4", "nota_fiscal": "NF-10",
        }, follow=True)
        self.assertContains(resposta, "lote novo")
        self.assertContains(self.client.get(reverse("movimentacoes:lotes")), "Galpão C")

    def test_erros_de_regra_aparecem_no_formulario(self):
        casos = {
            "Chapas exigem largura": {"id_material": "1", "localizacao": "X", "quantidade": "1", "nota_fiscal": "N"},
            "número inteiro": {"id_estoque": "1", "quantidade": "1,5", "nota_fiscal": "N"},
            "Escolha um lote existente ou o material": {"quantidade": "1", "nota_fiscal": "N"},
            "não os dois": {"id_estoque": "1", "id_material": "1", "quantidade": "1", "nota_fiscal": "N"},
            "obrigatório": {"id_estoque": "1", "quantidade": "1", "nota_fiscal": ""},
        }
        for trecho, dados in casos.items():
            with self.subTest(trecho):
                resposta = self.client.post(self.url, dados)
                self.assertContains(resposta, trecho)
                self.assertEqual(resposta.status_code, 200)  # continua no formulário


class TestePerda(BaseViewTest):
    def setUp(self):
        super().setUp()
        self.entrar("demo.producao")
        self.url = reverse("movimentacoes:perda")

    def test_lote_vem_preselecionado_pela_url(self):
        resposta = self.client.get(self.url + "?lote=2")
        self.assertContains(resposta, '<option value="2" selected>')

    def test_perda_registrada_aparece_no_historico(self):
        resposta = self.client.post(self.url, {"id_estoque": "1", "quantidade": "1", "categoria": "quebra",
                                               "motivo": "Caiu na descarga"}, follow=True)
        self.assertContains(resposta, "Perda registrada")
        self.assertContains(resposta, "Quebra: Caiu na descarga")
        self.assertContains(resposta, "Operador de produção")

    def test_nao_deixa_perder_material_reservado(self):
        resposta = self.client.post(self.url, {"id_estoque": "1", "quantidade": "2", "categoria": "quebra", "motivo": "x"})
        self.assertContains(resposta, "reservado para pedidos")

    def test_lote_sem_disponivel_nem_aparece(self):
        # lote 1 tem 1 disponível; depois da perda não sobra nada para escolher
        self.client.post(self.url, {"id_estoque": "1", "quantidade": "1", "categoria": "defeito", "motivo": "trinca"})
        self.assertNotContains(self.client.get(self.url), "#1 VID-T8")


class TesteAjuste(BaseViewTest):
    def setUp(self):
        super().setUp()
        self.entrar("teste.admin")
        self.url = reverse("movimentacoes:ajuste")

    def test_ajuste_registrado_com_sistema_e_contado(self):
        resposta = self.client.post(self.url, {"id_estoque": "1", "quantidade_contada": "4",
                                               "justificativa": "Achamos 2 chapas no fundo"}, follow=True)
        self.assertContains(resposta, "Ajuste registrado")
        self.assertContains(resposta, "sistema: 2, contado: 4")

    def test_contagem_igual_ou_abaixo_do_reservado_e_recusada(self):
        for contada, trecho in (("2", "não há o que ajustar"), ("0", "menor que o reservado")):
            with self.subTest(contada):
                resposta = self.client.post(self.url, {"id_estoque": "1", "quantidade_contada": contada,
                                                       "justificativa": "teste"})
                self.assertContains(resposta, trecho)

    def test_funcionario_do_estoque_nao_ajusta(self):
        self.entrar("demo.estoque")
        resposta = self.client.post(self.url, {"id_estoque": "1", "quantidade_contada": "3", "justificativa": "x"})
        self.assertContains(resposta, "Sem permissão", status_code=403)


class TesteHistorico(BaseViewTest):
    def test_historico_e_filtros(self):
        self.entrar("demo.estoque")
        url = reverse("movimentacoes:historico")
        resposta = self.client.get(url)
        self.assertContains(resposta, "NF-DEMO-001")
        self.assertIn("entrega", {m["tipo"] for m in resposta.context["movimentacoes"]})
        self.assertNotContains(self.client.get(url, {"tipo": "perda"}), "NF-DEMO-001")
        self.assertContains(self.client.get(url, {"id_material": "2"}), "NF-DEMO-002")
        self.assertNotContains(self.client.get(url, {"id_material": "2"}), "NF-DEMO-001")
        self.assertContains(self.client.get(url, {"data_inicio": "2000-01-01", "data_fim": "2000-12-31"}),
                            "Nenhuma movimentação")

    def test_lotes_busca(self):
        self.entrar("demo.estoque")
        url = reverse("movimentacoes:lotes")
        self.assertContains(self.client.get(url, {"q": "perfil"}), "PER-01")
        self.assertNotContains(self.client.get(url, {"q": "perfil"}), "VID-T8")
