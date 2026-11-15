from django.test import TestCase
from django.urls import reverse

from cadastros.models import Fornecedor
from cadastros.validators import completar_cnpj, completar_cpf

from .test_materiais import BaseTest

CNPJ = completar_cnpj("123456780001")
CPF = completar_cpf("123456789")


def dados_fornecedor(**extra):
    dados = {"nome": "Vidros do Sul Ltda", "telefone": "(11) 98765-4321", "ativo": "on"}
    dados.update(extra)
    return dados


class FornecedorCadastroTest(BaseTest):
    def post(self, **extra):
        return self.client.post(reverse("cadastros:fornecedor_create"), dados_fornecedor(**extra))

    def test_cadastra_com_cnpj_mascarado_e_guarda_so_digitos(self):
        mascarado = f"{CNPJ[:2]}.{CNPJ[2:5]}.{CNPJ[5:8]}/{CNPJ[8:12]}-{CNPJ[12:]}"
        self.post(cpf_cnpj=mascarado)
        fornecedor = Fornecedor.objects.get()
        self.assertEqual(fornecedor.cpf_cnpj, CNPJ)
        self.assertEqual(fornecedor.telefone, "11987654321")
        self.assertEqual(fornecedor.cpf_cnpj_formatado, mascarado)

    def test_aceita_cpf_valido(self):
        self.post(cpf_cnpj=CPF)
        self.assertEqual(Fornecedor.objects.get().cpf_cnpj, CPF)

    def test_rejeita_documento_invalido(self):
        for invalido in ("12345678901", "11111111111", "123", CNPJ[:-1] + str((int(CNPJ[-1]) + 1) % 10)):
            resposta = self.post(cpf_cnpj=invalido)
            self.assertEqual(resposta.status_code, 200, invalido)
        self.assertFalse(Fornecedor.objects.exists())

    def test_cpf_cnpj_duplicado_e_recusado(self):
        self.post(cpf_cnpj=CNPJ)
        resposta = self.post(cpf_cnpj=CNPJ, nome="Outro nome")
        self.assertContains(resposta, "Já existe um fornecedor com este CPF/CNPJ.")
        self.assertEqual(Fornecedor.objects.count(), 1)

    def test_varios_sem_documento_e_nomes_repetidos_sao_permitidos(self):
        self.post()
        self.post()
        self.assertEqual(Fornecedor.objects.count(), 2)
        self.assertEqual(Fornecedor.objects.filter(cpf_cnpj__isnull=True).count(), 2)

    def test_telefone_obrigatorio_e_validado(self):
        self.assertEqual(self.post(telefone="").status_code, 200)
        self.assertEqual(self.post(telefone="123").status_code, 200)
        self.assertFalse(Fornecedor.objects.exists())

    def test_edita_mantendo_proprio_documento(self):
        self.post(cpf_cnpj=CNPJ)
        fornecedor = Fornecedor.objects.get()
        resposta = self.client.post(
            reverse("cadastros:fornecedor_update", args=[fornecedor.pk]),
            dados_fornecedor(cpf_cnpj=CNPJ, nome="Nome atualizado"),
        )
        self.assertEqual(resposta.status_code, 302)
        fornecedor.refresh_from_db()
        self.assertEqual(fornecedor.nome, "Nome atualizado")


class FornecedorBuscaEInativacaoTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.a = Fornecedor.objects.create(nome="Vidros do Sul", cpf_cnpj=CNPJ, telefone="11987654321")
        self.b = Fornecedor.objects.create(nome="Ferragens Brasil", nome_fantasia="FerBras", telefone="1133334444")

    def nomes(self, **params):
        resposta = self.client.get(reverse("cadastros:fornecedor_list"), params)
        return {f.nome for f in resposta.context["fornecedores"]}

    def test_busca_por_nome_e_fantasia(self):
        self.assertEqual(self.nomes(q="vidros"), {"Vidros do Sul"})
        self.assertEqual(self.nomes(q="ferbras"), {"Ferragens Brasil"})

    def test_busca_por_cnpj_com_ou_sem_mascara(self):
        mascarado = f"{CNPJ[:2]}.{CNPJ[2:5]}.{CNPJ[5:8]}/{CNPJ[8:12]}-{CNPJ[12:]}"
        self.assertEqual(self.nomes(q=mascarado), {"Vidros do Sul"})
        self.assertEqual(self.nomes(q=CNPJ[:8]), {"Vidros do Sul"})

    def test_inativa_reativa_por_post(self):
        self.client.post(reverse("cadastros:fornecedor_inativar", args=[self.a.pk]))
        self.a.refresh_from_db()
        self.assertFalse(self.a.ativo)
        self.assertEqual(self.nomes(situacao="inativo"), {"Vidros do Sul"})
        self.assertEqual(self.client.get(reverse("cadastros:fornecedor_reativar", args=[self.a.pk])).status_code, 405)
        self.client.post(reverse("cadastros:fornecedor_reativar", args=[self.a.pk]))
        self.a.refresh_from_db()
        self.assertTrue(self.a.ativo)
