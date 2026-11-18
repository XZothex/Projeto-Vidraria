from django.urls import reverse

from cadastros.validators import completar_cnpj, completar_cpf
from pedidos.models import Cliente

from .base import BaseTest

CNPJ = completar_cnpj("123456780001")
CPF = completar_cpf("123456789")


def dados(**extra):
    d = {"nome": "Cliente Novo", "telefone": "(11) 91234-5678", "ativo": "on"}
    d.update(extra)
    return d


class ClienteTest(BaseTest):
    def post(self, **extra):
        return self.client.post(reverse("pedidos:cliente_create"), dados(**extra))

    def test_exige_login(self):
        self.client.logout()
        for nome in ("cliente_list", "pedido_list"):
            resposta = self.client.get(reverse(f"pedidos:{nome}"))
            self.assertEqual(resposta.status_code, 302)
            self.assertIn("/entrar/", resposta.url)

    def test_cadastra_guardando_so_digitos(self):
        mascarado = f"{CNPJ[:2]}.{CNPJ[2:5]}.{CNPJ[5:8]}/{CNPJ[8:12]}-{CNPJ[12:]}"
        self.post(cpf_cnpj=mascarado)
        cliente = Cliente.objects.get(nome="Cliente Novo")
        self.assertEqual(cliente.cpf_cnpj, CNPJ)
        self.assertEqual(cliente.telefone, "11912345678")
        self.assertEqual(cliente.cpf_cnpj_formatado, mascarado)

    def test_documento_invalido_e_duplicado(self):
        self.post(cpf_cnpj=CPF)
        self.assertContains(self.post(cpf_cnpj=CPF, nome="Outro"), "Já existe um cliente com este CPF/CNPJ.")
        self.assertEqual(self.post(cpf_cnpj="11111111111").status_code, 200)
        self.assertEqual(Cliente.objects.filter(cpf_cnpj__isnull=False).count(), 1)

    def test_varios_sem_documento(self):
        self.post()
        self.post()
        self.assertEqual(Cliente.objects.filter(nome="Cliente Novo").count(), 2)

    def test_telefone_obrigatorio(self):
        self.assertEqual(self.post(telefone="").status_code, 200)
        self.assertFalse(Cliente.objects.filter(nome="Cliente Novo").exists())

    def test_inativar_e_reativar_somente_post(self):
        url = reverse("pedidos:cliente_inativar", args=[self.cliente.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.ativo)
        self.client.post(reverse("pedidos:cliente_reativar", args=[self.cliente.pk]))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.ativo)

    def test_busca_por_nome_e_documento(self):
        Cliente.objects.create(nome="Zeca", telefone="11999999999", cpf_cnpj=CPF)
        url = reverse("pedidos:cliente_list")
        self.assertContains(self.client.get(url, {"q": "zeca"}), "Zeca")
        self.assertNotContains(self.client.get(url, {"q": "zeca"}), "Maria Souza")
        self.assertContains(self.client.get(url, {"q": f"{CPF[:3]}.{CPF[3:6]}"}), "Zeca")
