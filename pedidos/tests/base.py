from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from cadastros.models import Material
from pedidos.models import Cliente, ItemPedido, Pedido


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user("teste", password="senha-teste-123")
        cls.cliente = Cliente.objects.create(nome="Maria Souza", telefone="11987654321")
        cls.vidro = Material.objects.create(
            codigo="VID-1", nome="Vidro temperado 8 mm", categoria="vidro", unidade_controle="chapa"
        )
        cls.perfil = Material.objects.create(
            codigo="PER-1", nome="Perfil de alumínio", categoria="perfil_aluminio", unidade_controle="metro"
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def novo_pedido(self, itens=((None, "2"),), **extra):
        """Cria pedido com itens [(material, quantidade)]; material None = vidro."""
        pedido = Pedido.objects.create(cliente=self.cliente, criado_por=self.usuario, **extra)
        for material, qtd in itens:
            ItemPedido.objects.create(pedido=pedido, material=material or self.vidro, quantidade=Decimal(qtd))
        return pedido
