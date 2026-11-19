from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Material
from pedidos.models import Cliente, ItemPedido, Pedido, Reserva


class PainelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user("painel")
        material = Material.objects.create(
            codigo="TESTE", nome="Vidro de teste", categoria="vidro", unidade_controle="chapa",
        )
        for nome in ("Cliente Visível", "Cliente Oculto"):
            cliente = Cliente.objects.create(nome=nome)
            pedido = Pedido.objects.create(cliente=cliente)
            item = ItemPedido.objects.create(pedido=pedido, material=material, quantidade=1)
            Reserva.objects.create(item=item, quantidade=1, criada_por=cls.usuario)

    def test_painel_exige_login(self):
        self.assertEqual(self.client.get(reverse("painel:dashboard")).status_code, 302)

    def test_tela_e_csv_usam_o_mesmo_filtro(self):
        self.client.force_login(self.usuario)
        for tipo in ("reservas", "pedidos", "movimentacoes"):
            with self.subTest(tipo=tipo):
                url = reverse("painel:relatorio", args=[tipo])
                for parametros in ({"q": "Visível"}, {"q": "Visível", "exportar": "csv"}):
                    resposta = self.client.get(url, parametros)
                    self.assertContains(resposta, "Cliente Visível")
                    self.assertNotContains(resposta, "Cliente Oculto")

    def test_historico_trata_pagina_invalida_e_exporta_utf8(self):
        self.client.force_login(self.usuario)
        url = reverse("painel:historico")
        self.assertContains(self.client.get(url, {"page": "²"}), "Página 1 de 1")
        csv = self.client.get(url, {"exportar": "csv", "q": "Visível"})
        self.assertTrue(csv.content.startswith(b"\xef\xbb\xbf"))
        self.assertContains(csv, "Cliente Visível")
        self.assertNotContains(csv, "Cliente Oculto")
