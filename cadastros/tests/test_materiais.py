from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Material


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user("teste", password="senha-teste-123")

    def setUp(self):
        self.client.force_login(self.usuario)


def dados_material(**extra):
    dados = {
        "codigo": "VID-001", "nome": "Vidro temperado 8 mm", "categoria": "vidro",
        "unidade_controle": "chapa", "tipo_vidro": "temperado", "cor": "Incolor",
        "espessura_mm": "8.00", "ativo": "on",
    }
    dados.update(extra)
    return dados


class MaterialCadastroTest(BaseTest):
    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("cadastros:material_list"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/entrar/", resposta.url)

    def test_cadastra_material_valido(self):
        resposta = self.client.post(reverse("cadastros:material_create"), dados_material(codigo="vid-001"))
        material = Material.objects.get()
        self.assertRedirects(resposta, material.get_absolute_url())
        self.assertEqual(material.codigo, "VID-001")  # normalizado em maiúsculas
        self.assertEqual(material.espessura_mm, Decimal("8.00"))

    def test_ferragem_sem_campos_de_vidro(self):
        dados = dados_material(codigo="FER-1", nome="Dobradiça", categoria="ferragem",
                               unidade_controle="unidade", tipo_vidro="", cor="", espessura_mm="")
        self.client.post(reverse("cadastros:material_create"), dados)
        material = Material.objects.get(codigo="FER-1")
        self.assertIsNone(material.espessura_mm)

    def test_codigo_duplicado_ignora_maiusculas(self):
        self.client.post(reverse("cadastros:material_create"), dados_material())
        resposta = self.client.post(reverse("cadastros:material_create"), dados_material(codigo="vid-001"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe um material com este código.")
        self.assertEqual(Material.objects.count(), 1)

    def test_espessura_deve_ser_positiva(self):
        for valor in ("0", "-3"):
            resposta = self.client.post(reverse("cadastros:material_create"), dados_material(espessura_mm=valor))
            self.assertEqual(resposta.status_code, 200)
            self.assertFalse(Material.objects.exists())

    def test_campos_obrigatorios(self):
        resposta = self.client.post(reverse("cadastros:material_create"), {})
        self.assertEqual(resposta.status_code, 200)
        for campo in ("codigo", "nome", "categoria", "unidade_controle"):
            self.assertIn(campo, resposta.context["form"].errors)

    def test_edita_material_mantendo_proprio_codigo(self):
        material = Material.objects.create(codigo="A1", nome="Antigo", categoria="outro", unidade_controle="unidade")
        resposta = self.client.post(
            reverse("cadastros:material_update", args=[material.pk]),
            dados_material(codigo="A1", nome="Novo nome", categoria="outro", unidade_controle="unidade",
                           tipo_vidro="", cor="", espessura_mm=""),
        )
        self.assertEqual(resposta.status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.nome, "Novo nome")


class MaterialListagemTest(BaseTest):
    def setUp(self):
        super().setUp()
        Material.objects.create(codigo="VID-1", nome="Vidro temperado", categoria="vidro", unidade_controle="chapa")
        Material.objects.create(codigo="FER-1", nome="Dobradiça", categoria="ferragem", unidade_controle="unidade")
        Material.objects.create(codigo="FER-2", nome="Puxador", categoria="ferragem", unidade_controle="unidade", ativo=False)

    def codigos(self, **params):
        resposta = self.client.get(reverse("cadastros:material_list"), params)
        return {m.codigo for m in resposta.context["materiais"]}

    def test_pesquisa_por_nome_e_codigo(self):
        self.assertEqual(self.codigos(q="temperado"), {"VID-1"})
        self.assertEqual(self.codigos(q="fer-"), {"FER-1", "FER-2"})

    def test_filtra_por_categoria_e_situacao(self):
        self.assertEqual(self.codigos(categoria="ferragem"), {"FER-1", "FER-2"})
        self.assertEqual(self.codigos(categoria="ferragem", situacao="ativo"), {"FER-1"})
        self.assertEqual(self.codigos(situacao="inativo"), {"FER-2"})

    def test_paginacao_preserva_filtros(self):
        for i in range(25):
            Material.objects.create(codigo=f"X-{i:02}", nome=f"Item {i}", categoria="outro", unidade_controle="unidade")
        resposta = self.client.get(reverse("cadastros:material_list"), {"categoria": "outro"})
        self.assertEqual(len(resposta.context["materiais"]), 10)
        self.assertContains(resposta, "categoria=outro&page=2")
        resposta = self.client.get(reverse("cadastros:material_list"), {"categoria": "outro", "page": 3})
        self.assertEqual(len(resposta.context["materiais"]), 5)


class MaterialInativacaoTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.material = Material.objects.create(codigo="A1", nome="A", categoria="outro", unidade_controle="unidade")

    def test_inativa_e_reativa_por_post_sem_apagar(self):
        self.client.post(reverse("cadastros:material_inativar", args=[self.material.pk]))
        self.material.refresh_from_db()
        self.assertFalse(self.material.ativo)
        self.client.post(reverse("cadastros:material_reativar", args=[self.material.pk]))
        self.material.refresh_from_db()
        self.assertTrue(self.material.ativo)
        self.assertEqual(Material.objects.count(), 1)

    def test_get_nao_altera_dados(self):
        resposta = self.client.get(reverse("cadastros:material_inativar", args=[self.material.pk]))
        self.assertEqual(resposta.status_code, 405)
        self.material.refresh_from_db()
        self.assertTrue(self.material.ativo)

    def test_post_exige_csrf(self):
        from django.test import Client
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        resposta = cliente.post(reverse("cadastros:material_inativar", args=[self.material.pk]))
        self.assertEqual(resposta.status_code, 403)
