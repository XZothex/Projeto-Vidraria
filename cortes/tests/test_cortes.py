from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from cadastros.models import Material
from pedidos.models import Cliente, ItemPedido, Pedido
from cortes.models import ChapaDisponivel, OperacaoCorte
from cortes.services import registrar_operacao


class RegistroCorteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="cortador", password="senha-forte-123")
        cls.material = Material.objects.create(codigo="VID-CORTE", nome="Vidro temperado 8 mm", categoria="vidro", unidade_controle="chapa", espessura_mm=8)
        cliente = Cliente.objects.create(nome="Cliente Teste", telefone="11987654321")
        pedido = Pedido.objects.create(cliente=cliente)
        cls.item = ItemPedido.objects.create(pedido=pedido, material=cls.material, quantidade=1)
        cls.pedido = pedido

    def operacao_manual(self):
        return OperacaoCorte(
            pedido=self.pedido, item_pedido=self.item, material=self.material,
            origem=OperacaoCorte.Origem.MANUAL, largura_chapa_mm=Decimal("3000"),
            altura_chapa_mm=Decimal("2000"), espessura_mm=Decimal("8"),
            quantidade_chapas=1, kerf_mm=Decimal("3"),
        )

    def test_registra_peca_e_sobra_reaproveitavel(self):
        op = registrar_operacao(
            operacao=self.operacao_manual(), usuario=self.user,
            pecas=[{"identificacao": "Porta", "largura_mm": Decimal("800"), "altura_mm": Decimal("1800"), "quantidade": 1}],
            sobras=[{"largura_mm": Decimal("500"), "altura_mm": Decimal("1800"), "observacoes": "Sobra lateral"}],
        )
        self.assertEqual(op.pecas.count(), 1)
        self.assertEqual(op.sobras.count(), 1)
        self.assertEqual(ChapaDisponivel.objects.filter(tipo=ChapaDisponivel.Tipo.SOBRA, status=ChapaDisponivel.Status.DISPONIVEL).count(), 1)

    def test_rejeita_peca_maior_que_chapa(self):
        with self.assertRaises(ValidationError):
            registrar_operacao(
                operacao=self.operacao_manual(), usuario=self.user,
                pecas=[{"identificacao": "Inviável", "largura_mm": Decimal("3500"), "altura_mm": Decimal("1800"), "quantidade": 1}],
                sobras=[],
            )
