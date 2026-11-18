"""Cria clientes e pedidos FICTÍCIOS de demonstração. Pode ser repetido (não duplica).

Antes, rode:  python manage.py popular_cadastros   (os pedidos usam esses materiais)
Uso:          python manage.py popular_pedidos
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from cadastros.models import Material
from cadastros.validators import completar_cpf
from pedidos import services
from pedidos.models import Cliente, ItemPedido, Pedido

CLIENTES = [
    # nome, documento (ou None), telefone, email, endereco
    ("Maria Souza", completar_cpf("111222333"), "11988887777", "maria@example.com", "Rua das Acácias, 10 - São Paulo/SP"),
    ("Construtora Alfa Ltda", None, "1133332222", "obras@alfa.example", "Av. das Obras, 900 - Campinas/SP"),
    ("Carlos Pereira", None, "21977776666", "", ""),
]

# cliente -> [(codigo do material, quantidade, especificacao)] + estado desejado
PEDIDOS = [
    ("Maria Souza", "aberto", [("VID-TEMP-8-INC", "2", "Box 80 x 190 cm"), ("FER-DOBR-001", "4", "")]),
    ("Construtora Alfa Ltda", "reservado", [("VID-LAM-8-INC", "3", "Janelas do 2º andar"), ("PER-JAN-FOSCO", "12.5", "Barras de 6 m")]),
    ("Carlos Pereira", "entregue", [("VID-ESP-4", "1", "Espelho 60 x 160 cm")]),
]


class Command(BaseCommand):
    help = "Cria clientes e pedidos fictícios de demonstração (idempotente)."

    def handle(self, *args, **opcoes):
        usuario = get_user_model().objects.filter(is_superuser=True).first()
        criados = 0
        for nome, documento, telefone, email, endereco in CLIENTES:
            _, novo = Cliente.objects.get_or_create(
                nome=nome,
                defaults={"cpf_cnpj": documento, "telefone": telefone, "email": email, "endereco": endereco,
                          "observacoes": "Dado fictício de demonstração."},
            )
            criados += novo
        self.stdout.write(f"Clientes novos: {criados}")

        if Pedido.objects.filter(observacoes__startswith="[demo]").exists():
            self.stdout.write("Pedidos de demonstração já existem; nada a fazer.")
            return
        for nome, estado, itens in PEDIDOS:
            pedido = Pedido.objects.create(
                cliente=Cliente.objects.get(nome=nome), criado_por=usuario,
                observacoes="[demo] Dado fictício de demonstração.",
                data_prevista=timezone.localdate() + timedelta(days=7),
            )
            for codigo, qtd, spec in itens:
                try:
                    material = Material.objects.get(codigo=codigo)
                except Material.DoesNotExist:
                    pedido.delete()
                    raise CommandError(f"Material {codigo} não existe. Rode antes: python manage.py popular_cadastros")
                ItemPedido.objects.create(pedido=pedido, material=material, quantidade=Decimal(qtd), especificacao=spec)
            if estado in ("reservado", "entregue"):
                services.reservar(pedido, usuario)
            if estado == "entregue":
                services.registrar_entrega(pedido, usuario, timezone.localdate(), "Carlos Pereira", "Entrega de demonstração.")
        self.stdout.write(self.style.SUCCESS("Pedidos de demonstração criados."))
