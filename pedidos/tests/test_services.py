from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.utils import timezone

from pedidos import services
from pedidos.models import Entrega, Pedido, Reserva
from pedidos.services import RegraDeNegocioError

from .base import BaseTest


class ReservaTest(BaseTest):
    def test_reservar_e_liberar_todos(self):
        pedido = self.novo_pedido([(None, "2"), (self.perfil, "3.5")])
        self.assertEqual(services.reservar(pedido, self.usuario), 2)
        self.assertEqual(Reserva.objects.filter(status="ativa").count(), 2)
        self.assertEqual(services.liberar(pedido, self.usuario), 2)
        self.assertEqual(Reserva.objects.filter(status="liberada").count(), 2)
        self.assertFalse(Reserva.objects.filter(status="ativa").exists())

    def test_nao_reserva_duas_vezes(self):
        pedido = self.novo_pedido()
        services.reservar(pedido, self.usuario)
        with self.assertRaises(RegraDeNegocioError):
            services.reservar(pedido, self.usuario)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_reservar_apenas_um_item(self):
        pedido = self.novo_pedido([(None, "1"), (self.perfil, "2")])
        item = pedido.itens.first()
        services.reservar(pedido, self.usuario, itens=[item])
        self.assertEqual(Reserva.objects.filter(status="ativa").count(), 1)
        services.liberar(pedido, self.usuario, itens=[item])
        self.assertFalse(Reserva.objects.filter(status="ativa").exists())

    def test_item_de_outro_pedido_e_recusado(self):
        a, b = self.novo_pedido(), self.novo_pedido()
        with self.assertRaises(RegraDeNegocioError):
            services.reservar(a, self.usuario, itens=[b.itens.first()])

    def test_liberar_sem_reserva_e_erro(self):
        with self.assertRaises(RegraDeNegocioError):
            services.liberar(self.novo_pedido(), self.usuario)

    def test_reserva_do_material_inativo_e_recusada(self):
        pedido = self.novo_pedido()
        self.vidro.ativo = False
        self.vidro.save()
        with self.assertRaisesMessage(RegraDeNegocioError, "inativo"):
            services.reservar(pedido, self.usuario)

    def test_estoque_insuficiente_nao_reserva_nada(self):
        pedido = self.novo_pedido([(None, "3"), (self.perfil, "1")])
        saldos = {self.vidro.pk: Decimal("2"), self.perfil.pk: Decimal("10")}
        with mock.patch("pedidos.estoque.saldo_fisico", side_effect=lambda m: saldos[m.pk]):
            with self.assertRaisesMessage(RegraDeNegocioError, "VID-1"):
                services.reservar(pedido, self.usuario)
        self.assertFalse(Reserva.objects.exists())  # tudo ou nada

    def test_disponibilidade_desconta_reservas_de_outros_pedidos(self):
        p1, p2 = self.novo_pedido([(None, "3")]), self.novo_pedido([(None, "3")])
        with mock.patch("pedidos.estoque.saldo_fisico", return_value=Decimal("5")):
            services.reservar(p1, self.usuario)
            with self.assertRaisesMessage(RegraDeNegocioError, "disponível 2"):
                services.reservar(p2, self.usuario)
            services.liberar(p1, self.usuario)  # liberou -> volta a ficar disponível
            services.reservar(p2, self.usuario)

    def test_mesmo_material_em_dois_itens_soma_a_necessidade(self):
        pedido = self.novo_pedido([(None, "3"), (None, "3")])
        with mock.patch("pedidos.estoque.saldo_fisico", return_value=Decimal("5")):
            with self.assertRaises(RegraDeNegocioError):
                services.reservar(pedido, self.usuario)


class CancelamentoTest(BaseTest):
    def test_cancelar_libera_reservas(self):
        pedido = self.novo_pedido([(None, "1"), (self.perfil, "2")])
        services.reservar(pedido, self.usuario)
        services.cancelar(pedido, self.usuario, "Cliente desistiu")
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, Pedido.Status.CANCELADO)
        self.assertEqual(pedido.motivo_cancelamento, "Cliente desistiu")
        self.assertEqual(pedido.cancelado_por, self.usuario)
        self.assertIsNotNone(pedido.cancelado_em)
        self.assertFalse(Reserva.objects.filter(status="ativa").exists())
        self.assertEqual(Reserva.objects.filter(status="liberada").count(), 2)

    def test_motivo_obrigatorio(self):
        with self.assertRaises(RegraDeNegocioError):
            services.cancelar(self.novo_pedido(), self.usuario, "   ")

    def test_pedido_cancelado_nao_muda_mais(self):
        pedido = self.novo_pedido()
        services.cancelar(pedido, self.usuario, "x")
        for acao in (
            lambda: services.reservar(pedido, self.usuario),
            lambda: services.liberar(pedido, self.usuario),
            lambda: services.cancelar(pedido, self.usuario, "de novo"),
            lambda: services.registrar_entrega(pedido, self.usuario, timezone.localdate(), "Fulano"),
            lambda: services.remover_item(pedido.itens.first()),
        ):
            with self.assertRaises(RegraDeNegocioError):
                acao()


class EntregaTest(BaseTest):
    def entregar(self, pedido, **extra):
        dados = dict(data_entrega=timezone.localdate(), recebido_por="João", observacoes="")
        dados.update(extra)
        return services.registrar_entrega(pedido, self.usuario, **dados)

    def test_entrega_consome_reservas_e_fecha_pedido(self):
        pedido = self.novo_pedido()
        services.reservar(pedido, self.usuario)
        self.entregar(pedido)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, Pedido.Status.ENTREGUE)
        self.assertEqual(Reserva.objects.get().status, Reserva.Status.CONSUMIDA)
        entrega = Entrega.objects.get()
        self.assertEqual((entrega.recebido_por, entrega.registrado_por), ("João", self.usuario))

    def test_exige_todos_os_itens_reservados(self):
        pedido = self.novo_pedido([(None, "1"), (self.perfil, "2")])
        services.reservar(pedido, self.usuario, itens=[pedido.itens.first()])
        with self.assertRaisesMessage(RegraDeNegocioError, "Reserve todos"):
            self.entregar(pedido)
        pedido.refresh_from_db()
        self.assertTrue(pedido.aberto)

    def test_pedido_sem_itens_nao_entrega(self):
        with self.assertRaises(RegraDeNegocioError):
            self.entregar(self.novo_pedido([]))

    def test_data_futura_recusada_sem_alterar_nada(self):
        pedido = self.novo_pedido()
        services.reservar(pedido, self.usuario)
        with self.assertRaises(RegraDeNegocioError):
            self.entregar(pedido, data_entrega=timezone.localdate() + timedelta(days=1))
        self.assertEqual(Reserva.objects.get().status, Reserva.Status.ATIVA)
        self.assertFalse(Entrega.objects.exists())

    def test_nao_entrega_duas_vezes_nem_cancela_depois(self):
        pedido = self.novo_pedido()
        services.reservar(pedido, self.usuario)
        self.entregar(pedido)
        with self.assertRaises(RegraDeNegocioError):
            self.entregar(pedido)
        with self.assertRaises(RegraDeNegocioError):
            services.cancelar(pedido, self.usuario, "tarde demais")


class ItemTest(BaseTest):
    def test_item_reservado_nao_edita_nem_remove(self):
        pedido = self.novo_pedido()
        item = pedido.itens.first()
        services.reservar(pedido, self.usuario)
        with self.assertRaises(RegraDeNegocioError):
            services.remover_item(item)
        item.quantidade = Decimal("9")
        with self.assertRaises(RegraDeNegocioError):
            services.salvar_item(item)
        services.liberar(pedido, self.usuario)
        services.salvar_item(item)
        services.remover_item(item)
        self.assertFalse(pedido.itens.exists())
