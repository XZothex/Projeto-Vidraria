"""Cria dados FICTÍCIOS de demonstração. Pode ser executado várias vezes (não duplica).

Uso:  python manage.py popular_cadastros
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from cadastros.models import Fornecedor, Material
from cadastros.validators import completar_cnpj, completar_cpf

M = Material.Categoria
T = Material.TipoVidro
U = Material.Unidade

MATERIAIS = [
    # codigo, nome, categoria, unidade, tipo_vidro, cor, espessura, localizacao, descricao
    ("VID-COM-4-INC", "Vidro comum incolor 4 mm", M.VIDRO, U.CHAPA, T.COMUM, "Incolor", "4.00", "Galpão A - Rack 1", ""),
    ("VID-COM-6-INC", "Vidro comum incolor 6 mm", M.VIDRO, U.CHAPA, T.COMUM, "Incolor", "6.00", "Galpão A - Rack 1", ""),
    ("VID-TEMP-8-INC", "Vidro temperado incolor 8 mm", M.VIDRO, U.M2, T.TEMPERADO, "Incolor", "8.00", "Galpão A - Rack 2", "Para box e portas."),
    ("VID-TEMP-10-FUM", "Vidro temperado fumê 10 mm", M.VIDRO, U.M2, T.TEMPERADO, "Fumê", "10.00", "Galpão A - Rack 2", ""),
    ("VID-LAM-8-INC", "Vidro laminado incolor 8 mm", M.VIDRO, U.CHAPA, T.LAMINADO, "Incolor", "8.00", "Galpão A - Rack 3", ""),
    ("VID-ESP-4", "Espelho 4 mm", M.VIDRO, U.CHAPA, T.ESPELHO, "Prata", "4.00", "Galpão A - Rack 4", ""),
    ("PER-BOX-BRANCO", "Perfil de alumínio para box branco", M.PERFIL, U.METRO, "", "Branco", None, "Galpão B - Prateleira 1", "Barra de 6 m."),
    ("PER-JAN-FOSCO", "Perfil de alumínio para janela fosco", M.PERFIL, U.METRO, "", "Fosco", "1.20", "Galpão B - Prateleira 1", ""),
    ("FER-DOBR-001", "Dobradiça para vidro temperado", M.FERRAGEM, U.UNIDADE, "", "", None, "Armário 2", ""),
    ("FER-PUX-001", "Puxador tubular 40 cm", M.FERRAGEM, U.UNIDADE, "", "Inox", None, "Armário 2", ""),
    ("ACE-ROLD-001", "Roldana para janela de correr", M.ACESSORIO, U.UNIDADE, "", "", None, "Armário 3", ""),
    ("BOR-VED-001", "Borracha de vedação", M.BORRACHA, U.METRO, "", "Preta", None, "Galpão B - Prateleira 3", ""),
    ("OUT-SIL-001", "Silicone neutro", M.OUTRO, U.UNIDADE, "", "Transparente", None, "Armário 4", "Material inativo de exemplo."),
]

NOTA = "Dado fictício de demonstração."
FORNECEDORES = [
    # nome, fantasia, documento (ou None), telefone, email, endereco
    ("Vidros do Sul Ltda", "Vidros Sul", completar_cnpj("123456780001"), "11987654321", "contato@vidrossul.example", "Rua das Flores, 100 - São Paulo/SP"),
    ("Alumínios Horizonte S.A.", "Horizonte Alumínios", completar_cnpj("987654320001"), "1133334444", "vendas@horizonte.example", "Av. Central, 500 - Campinas/SP"),
    ("Ferragens Brasil Comércio ME", "Ferragens Brasil", completar_cnpj("456789010001"), "21988887777", "", "Rua do Comércio, 45 - Rio de Janeiro/RJ"),
    ("João da Silva (autônomo)", "", completar_cpf("123456789"), "11977776666", "", ""),
    ("Fornecedor sem documento", "", None, "1144445555", "", "Cadastro sem CPF/CNPJ para exemplo."),
    ("Borrachas e Vedações Ltda", "Vedabem", completar_cnpj("111222330001"), "1155556666", "contato@vedabem.example", ""),
]


class Command(BaseCommand):
    help = "Cria materiais e fornecedores fictícios para demonstração (idempotente)."

    def handle(self, *args, **opcoes):
        novos_m = 0
        for cod, nome, cat, un, tipo, cor, esp, loc, desc in MATERIAIS:
            _, criado = Material.objects.get_or_create(
                codigo=cod,
                defaults=dict(
                    nome=nome, categoria=cat, unidade_controle=un, tipo_vidro=tipo, cor=cor,
                    espessura_mm=Decimal(esp) if esp else None, localizacao_padrao=loc,
                    descricao=desc, ativo=(cod != "OUT-SIL-001"),
                ),
            )
            novos_m += criado

        novos_f = 0
        for nome, fantasia, doc, tel, email, end in FORNECEDORES:
            busca = {"cpf_cnpj": doc} if doc else {"cpf_cnpj__isnull": True, "nome": nome}
            existente = Fornecedor.objects.filter(**busca).first()
            if existente:
                continue
            Fornecedor.objects.create(
                nome=nome, nome_fantasia=fantasia, cpf_cnpj=doc, telefone=tel,
                email=email, endereco=end, observacoes=NOTA,
            )
            novos_f += 1

        self.stdout.write(self.style.SUCCESS(
            f"Demonstração pronta: {novos_m} material(is) e {novos_f} fornecedor(es) novos."
        ))
