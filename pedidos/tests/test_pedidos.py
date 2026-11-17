from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from pedidos.models import Cliente, ItemPedido, Pedido, Reserva

from .base import BaseTest


def u(nome, *args):
    return reverse(f"pedidos:{nome}", args=args)


class PedidoCriacaoTest(BaseTest):
    def test_cria_pedido_registrando_usuario(self):
        resposta = self.client.post(u("pedido_create"), {"cliente": self.cliente.pk, "observacoes": "urgente"})
        pedido = Pedido.objects.get()
        self.assertRedirects(resposta, pedido.get_absolute_url())
        self.assertEqual((pedido.criado_por, pedido.status), (self.usuario, "aberto"))

    def test_cliente_inativo_nao_pode_receber_pedido(self):
        self.cliente.ativo = False
        self.cliente.save()
        resposta = self.client.post(u("pedido_create"), {"cliente": self.cliente.pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Pedido.objects.exists())

    def test_data_prevista_no_passado_e_recusada(self):
        ontem = timezone.localdate() - timedelta(days=1)
        resposta = self.client.post(u("pedido_create"), {"cliente": self.cliente.pk, "data_prevista": ontem})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Pedido.objects.exists())

    def test_cliente_vem_preselecionado(self):
        resposta = self.client.get(u("pedido_create"), {"cliente": self.cliente.pk})
        self.assertEqual(resposta.context["form"].initial["cliente"], self.cliente.pk)

    def test_lista_filtra_por_status_cliente_e_numero(self):
        aberto = self.novo_pedido()
        cancelado = self.novo_pedido(status="cancelado")
        resposta = self.client.get(u("pedido_list"), {"status": "cancelado"})
        self.assertEqual([p.pk for p in resposta.context["pedidos"]], [cancelado.pk])
        resposta = self.client.get(u("pedido_list"), {"q": f"#{aberto.pk}"})
        self.assertEqual([p.pk for p in resposta.context["pedidos"]], [aberto.pk])
        resposta = self.client.get(u("pedido_list"), {"q": "maria"})
        self.assertEqual(resposta.context["paginator"].count, 2)


class ItemViewsTest(BaseTest):
    def test_adiciona_item_e_valida_quantidade(self):
        pedido = self.novo_pedido([])
        url = u("item_create", pedido.pk)
        self.client.post(url, {"material": self.vidro.pk, "quantidade": "0"})
        self.client.post(url, {"material": self.vidro.pk, "quantidade": "1.5"})  # chapa = inteiro
        self.assertFalse(pedido.itens.exists())
        resposta = self.client.post(url, {"material": self.perfil.pk, "quantidade": "1.5", "especificacao": "6 m"})
        self.assertRedirects(resposta, pedido.get_absolute_url())
        self.assertEqual(pedido.itens.get().quantidade, 1.5)

    def test_material_inativo_nao_aparece_nem_e_aceito(self):
        self.perfil.ativo = False
        self.perfil.save()
        pedido = self.novo_pedido([])
        resposta = self.client.post(u("item_create", pedido.pk), {"material": self.perfil.pk, "quantidade": "1"})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(pedido.itens.exists())

    def test_item_reservado_nao_edita_pela_tela(self):
        pedido = self.novo_pedido()
        item = pedido.itens.get()
        self.client.post(u("pedido_reservar", pedido.pk))
        resposta = self.client.post(
            u("item_update", pedido.pk, item.pk), {"material": self.vidro.pk, "quantidade": "9"}
        )
        self.assertContains(resposta, "Libere a reserva")
        item.refresh_from_db()
        self.assertEqual(item.quantidade, 2)

    def test_pedido_encerrado_bloqueia_edicoes(self):
        pedido = self.novo_pedido(status="cancelado")
        for url in (u("pedido_update", pedido.pk), u("item_create", pedido.pk), u("pedido_cancelar", pedido.pk)):
            resposta = self.client.get(url)
            self.assertRedirects(resposta, pedido.get_absolute_url())


class FluxoCompletoTest(BaseTest):
    def test_reserva_libera_reserva_e_entrega(self):
        pedido = self.novo_pedido([(None, "2"), (self.perfil, "3")])
        detalhe = self.client.get(pedido.get_absolute_url())
        self.assertContains(detalhe, "Não reservado")
        self.assertNotContains(detalhe, "Registrar entrega")

        self.client.post(u("pedido_reservar", pedido.pk))
        detalhe = self.client.get(pedido.get_absolute_url())
        self.assertContains(detalhe, "Reservado")
        self.assertContains(detalhe, "Registrar entrega")

        item = pedido.itens.first()
        self.client.post(u("item_liberar", pedido.pk, item.pk))
        self.assertNotContains(self.client.get(pedido.get_absolute_url()), "Registrar entrega")
        self.client.post(u("item_reservar", pedido.pk, item.pk))

        resposta = self.client.post(
            u("pedido_entregar", pedido.pk),
            {"data_entrega": timezone.localdate(), "recebido_por": "Maria", "observacoes": "ok"},
        )
        self.assertRedirects(resposta, pedido.get_absolute_url())
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "entregue")
        detalhe = self.client.get(pedido.get_absolute_url())
        self.assertContains(detalhe, "recebido por Maria")
        self.assertEqual(Reserva.objects.filter(status="consumida").count(), 2)

    def test_entrega_sem_reserva_mostra_erro_e_nao_altera(self):
        pedido = self.novo_pedido()
        resposta = self.client.post(
            u("pedido_entregar", pedido.pk),
            {"data_entrega": timezone.localdate(), "recebido_por": "Maria"},
        )
        self.assertContains(resposta, "Reserve todos os itens")
        pedido.refresh_from_db()
        self.assertTrue(pedido.aberto)

    def test_cancelamento_pela_tela(self):
        pedido = self.novo_pedido()
        self.client.post(u("pedido_reservar", pedido.pk))
        self.assertContains(self.client.post(u("pedido_cancelar", pedido.pk), {"motivo": ""}), "obrigatório")
        resposta = self.client.post(u("pedido_cancelar", pedido.pk), {"motivo": "Desistência"})
        self.assertRedirects(resposta, pedido.get_absolute_url())
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "cancelado")
        self.assertFalse(Reserva.objects.filter(status="ativa").exists())
        self.assertContains(self.client.get(pedido.get_absolute_url()), "Desistência")

    def test_acoes_so_aceitam_post(self):
        pedido = self.novo_pedido()
        item = pedido.itens.get()
        for url in (
            u("pedido_reservar", pedido.pk), u("pedido_liberar", pedido.pk),
            u("item_reservar", pedido.pk, item.pk), u("item_liberar", pedido.pk, item.pk),
            u("item_remover", pedido.pk, item.pk),
        ):
            self.assertEqual(self.client.get(url).status_code, 405, url)

    def test_erro_de_regra_vira_mensagem_na_tela(self):
        pedido = self.novo_pedido()
        resposta = self.client.post(u("pedido_liberar", pedido.pk), follow=True)
        self.assertContains(resposta, "Não há reservas ativas")

    def test_item_de_outro_pedido_da_404(self):
        a, b = self.novo_pedido(), self.novo_pedido()
        item_b = b.itens.get()
        self.assertEqual(self.client.post(u("item_reservar", a.pk, item_b.pk)).status_code, 404)

    def test_banco_impede_duas_reservas_ativas_no_mesmo_item(self):
        from django.db import IntegrityError, transaction

        pedido = self.novo_pedido()
        item = pedido.itens.get()
        Reserva.objects.create(item=item, quantidade=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reserva.objects.create(item=item, quantidade=1)
