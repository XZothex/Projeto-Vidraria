from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

Usuario = get_user_model()


class GerenciarContasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_superuser("admin", password="Senha-Do-Admin-38")
        cls.funcionario = Usuario.objects.create_user("funcionario", password="Senha-Do-Funcionario-39")

    def dados(self, username="novo"):
        return {
            "username": username, "first_name": "Conta", "password1": "Senha-Nova-7835",
            "password2": "Senha-Nova-7835",
        }

    def test_apenas_administrador_gerencia_contas(self):
        url = reverse("contas:usuarios")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.funcionario)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, self.dados()).status_code, 403)
        self.assertFalse(Usuario.objects.filter(username="novo").exists())

    def test_cadastro_usa_validadores_e_hash_do_django(self):
        self.client.force_login(self.admin)
        url = reverse("contas:usuarios")
        resposta = self.client.post(url, self.dados() | {"password1": "123", "password2": "123"})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username="novo").exists())
        self.assertRedirects(self.client.post(url, self.dados()), url)
        novo = Usuario.objects.get(username="novo")
        self.assertTrue(novo.check_password("Senha-Nova-7835"))
        self.assertFalse(novo.is_superuser)
        self.assertRedirects(self.client.post(url, self.dados("gestor") | {"administrador": "on"}), url)
        gestor = Usuario.objects.get(username="gestor")
        self.assertTrue(gestor.is_superuser and gestor.is_staff)

    def test_status_protege_a_propria_conta_e_bloqueia_acesso(self):
        conta = Client()
        conta.force_login(self.funcionario)
        self.client.force_login(self.admin)
        url = reverse("contas:alternar_status", args=[self.funcionario.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        sessao_csrf = Client(enforce_csrf_checks=True)
        sessao_csrf.force_login(self.admin)
        self.assertEqual(sessao_csrf.post(url, {"ativo": "0"}).status_code, 403)
        for _ in range(2):
            self.client.post(url, {"ativo": "0"})
        self.funcionario.refresh_from_db()
        self.assertFalse(self.funcionario.is_active)
        self.assertEqual(conta.get(reverse("painel:dashboard")).status_code, 302)
        self.assertFalse(conta.login(username="funcionario", password="Senha-Do-Funcionario-39"))
        self.client.post(url, {"ativo": "1"})
        self.assertTrue(conta.login(username="funcionario", password="Senha-Do-Funcionario-39"))
        self.client.post(reverse("contas:alternar_status", args=[self.admin.pk]), {"ativo": "0"})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
