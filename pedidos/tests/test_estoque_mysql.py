from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Material
from cortes.models import OperacaoCorte
from movimentacoes.tests.base import SQL_DIR, executar_script
from pedidos import estoque, services
from pedidos.models import Cliente, ItemPedido, Pedido, Reserva


@skipUnless(connection.vendor == "mysql", "Execute com DB_ENGINE=mysql.")
class EstoqueMySQLTest(TransactionTestCase):
    def test_reserva_concorrente_cancelamento_e_entrega_depois_do_corte(self):
        ddl = (SQL_DIR / "create_tables.sql").read_text(encoding="utf-8")
        executar_script(connection, ddl.split("USE estoque_vidracaria_v2;", 1)[1])
        dados = (SQL_DIR / "inserts.sql").read_text(encoding="utf-8")
        executar_script(connection, dados.split("USE estoque_vidracaria_v2;", 1)[1])
        usuario = get_user_model().objects.create_user("demo.estoque")
        cliente = Cliente.objects.create(nome="Cliente de teste")
        material = Material.objects.create(
            codigo="VID-T8", nome="Vidro", categoria="vidro", unidade_controle="chapa",
        )

        def pedido(quantidade):
            novo = Pedido.objects.create(cliente=cliente, criado_por=usuario)
            ItemPedido.objects.create(pedido=novo, material=material, quantidade=quantidade)
            return novo

        grande = pedido(10)
        with self.assertRaisesRegex(services.RegraDeNegocioError, "Disponibilidade insuficiente"):
            services.reservar(grande, usuario)
        grande.refresh_from_db()
        self.assertIsNone(grande.mysql_pedido_id)
        self.assertFalse(Reserva.objects.exists())

        inicio = Barrier(2, timeout=10)

        def competir(pedido):
            close_old_connections()
            try:
                inicio.wait()
                services.reservar(pedido, usuario)
                return pedido
            except services.RegraDeNegocioError as exc:
                self.assertIn("Disponibilidade insuficiente", str(exc))
                return None
            finally:
                close_old_connections()

        pedidos = [pedido(1), pedido(1)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            vencedores = [p for p in executor.map(competir, pedidos) if p is not None]
        self.assertEqual(len(vencedores), 1)
        self.assertEqual(estoque.quantidade_disponivel(material), 0)
        services.cancelar(vencedores[0], usuario, "Teste")
        self.assertEqual(estoque.quantidade_disponivel(material), 1)

        outro = next(p for p in pedidos if p.pk != vencedores[0].pk)
        services.reservar(outro, usuario)
        id_reserva = Reserva.objects.get(item__pedido=outro).mysql_reservas[0]
        item = outro.itens.get()
        self.client.force_login(usuario)
        resposta = self.client.post(reverse("cortes:novo"), {
            "pedido": outro.pk, "item_pedido": item.pk, "material": material.pk,
            "origem": "mysql", "kerf_mm": "3",
            "pecas-TOTAL_FORMS": "1", "pecas-INITIAL_FORMS": "0",
            "pecas-0-largura_mm": "1000", "pecas-0-altura_mm": "500", "pecas-0-quantidade": "1",
            "sobras-TOTAL_FORMS": "1", "sobras-INITIAL_FORMS": "0",
            "sobras-0-largura_mm": "500", "sobras-0-altura_mm": "500",
        })
        self.assertEqual(resposta.status_code, 302, resposta.context["form"].errors if resposta.context else "")
        corte = OperacaoCorte.objects.get(item_pedido=item)
        self.assertEqual(corte.pecas.count(), 1)
        sobra = corte.sobras.get()
        with connection.cursor() as cursor:
            cursor.execute("SELECT fisico, origem FROM saldo_estoque WHERE id_estoque = %s", [sobra.mysql_lote_id])
            self.assertEqual(cursor.fetchone(), (1, "sobra"))
        saldo = estoque.saldo_fisico(material)
        services.registrar_entrega(outro, usuario, timezone.localdate(), "Cliente")
        self.assertEqual(estoque.saldo_fisico(material), saldo)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT quantidade FROM movimentacao WHERE id_reserva = %s AND tipo = 'entrega'", [id_reserva],
            )
            self.assertEqual(cursor.fetchone()[0], 0)
