from io import StringIO
from decimal import Decimal

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from cadastros.forms import FornecedorForm
from cadastros.models import Material
from cadastros.validators import completar_cnpj


class DocumentoPreenchidoTest(TestCase):
    def test_rejeita_letras_e_caracteres_estranhos(self):
        documento = completar_cnpj('123456780001')
        for valor in ('abcdefgh', '---', 'abc' + documento, documento + '!'):
            with self.subTest(valor=valor):
                form = FornecedorForm(data={
                    'nome': 'Fornecedor', 'telefone': '11987654321', 'cpf_cnpj': valor,
                })
                self.assertFalse(form.is_valid())
                self.assertIn('cpf_cnpj', form.errors)


class CargaDemonstracaoTest(TestCase):
    def test_repeticao_preserva_edicoes_e_inativacao(self):
        call_command('popular_cadastros', stdout=StringIO())
        material = Material.objects.get(codigo='VID-COM-4-INC')
        material.nome = 'Nome alterado pelo usuario'
        material.espessura_mm = Decimal('5.00')
        material.ativo = False
        material.save()
        quantidade = Material.objects.count()
        call_command('popular_cadastros', stdout=StringIO())
        material.refresh_from_db()
        self.assertEqual(material.nome, 'Nome alterado pelo usuario')
        self.assertEqual(material.espessura_mm, Decimal('5.00'))
        self.assertFalse(material.ativo)
        self.assertEqual(Material.objects.count(), quantidade)


class RestricaoEspessuraTest(TestCase):
    def criar(self, codigo, espessura):
        return Material.objects.create(
            codigo=codigo, nome='Material', categoria='vidro',
            unidade_controle='chapa', espessura_mm=espessura,
        )

    def test_banco_recusa_zero_e_negativo(self):
        for valor in (0, -1):
            with self.subTest(valor=valor):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.criar('INVALIDO', valor)

    def test_banco_aceita_nulo_e_positivo(self):
        self.criar('SEM', None)
        self.criar('COM', Decimal('0.01'))
        self.assertEqual(Material.objects.count(), 2)

    def test_atualizacao_direta_nao_contorna_restricao(self):
        material = self.criar('OK', 8)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Material.objects.filter(pk=material.pk).update(espessura_mm=-1)
