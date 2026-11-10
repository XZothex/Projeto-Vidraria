"""Modelos do módulo de cadastros — PROPOSTA INICIAL para alinhar com o responsável pelo banco.

Decisões de modelagem (explicáveis ao professor):

* ``Material`` descreve o TIPO de material (ex.: "Vidro temperado incolor 8 mm"),
  e não uma chapa, peça ou sobra física. Largura, altura, quantidade, saldo,
  reservas e custo de aquisição variam por peça/recebimento e pertencem aos
  módulos de estoque (entradas, cortes e sobras). Por isso NÃO existem aqui.
* Não há vínculo fixo Material -> Fornecedor: o mesmo material pode ser comprado
  de vários fornecedores. O vínculo acontece nos recebimentos/pedidos.
* Nada é apagado: registros usados por outros módulos são apenas inativados.
  Os outros módulos devem apontar para estes modelos com ``on_delete=PROTECT``.
"""
from decimal import Decimal

from django.db import models
from django.urls import reverse

from .validators import (
    formatar_cpf_cnpj,
    formatar_telefone,
    somente_digitos,
    validar_cpf_cnpj,
    validar_positivo,
    validar_telefone,
)


class Material(models.Model):
    class Categoria(models.TextChoices):
        VIDRO = "vidro", "Vidro"
        PERFIL = "perfil_aluminio", "Perfil de alumínio"
        FERRAGEM = "ferragem", "Ferragem"
        ACESSORIO = "acessorio", "Acessório"
        BORRACHA = "borracha", "Borracha"
        OUTRO = "outro", "Outro"

    class TipoVidro(models.TextChoices):
        COMUM = "comum", "Comum (float)"
        TEMPERADO = "temperado", "Temperado"
        LAMINADO = "laminado", "Laminado"
        ESPELHO = "espelho", "Espelho"
        ARAMADO = "aramado", "Aramado"
        IMPRESSO = "impresso", "Impresso / fantasia"
        OUTRO = "outro", "Outro"

    class Unidade(models.TextChoices):
        CHAPA = "chapa", "Chapa"
        UNIDADE = "unidade", "Peça/unidade"
        METRO = "metro", "Metro"
        M2 = "m2", "Metro quadrado"

    codigo = models.CharField("Código", max_length=30, unique=True)
    nome = models.CharField("Nome", max_length=150)
    categoria = models.CharField("Categoria", max_length=20, choices=Categoria.choices)
    descricao = models.TextField("Descrição", blank=True)
    # Características opcionais: só fazem sentido para alguns materiais.
    tipo_vidro = models.CharField("Tipo de vidro", max_length=20, choices=TipoVidro.choices, blank=True)
    cor = models.CharField("Cor", max_length=50, blank=True)
    espessura_mm = models.DecimalField(
        "Espessura (mm)", max_digits=5, decimal_places=2, null=True, blank=True, validators=[validar_positivo]
    )
    unidade_controle = models.CharField("Unidade de controle", max_length=10, choices=Unidade.choices)
    localizacao_padrao = models.CharField("Localização padrão no estoque", max_length=100, blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome", "codigo"]
        verbose_name = "material"
        verbose_name_plural = "materiais"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(espessura_mm__isnull=True) | models.Q(espessura_mm__gt=0),
                name="material_espessura_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("cadastros:material_detail", args=[self.pk])


class Fornecedor(models.Model):
    nome = models.CharField("Nome / razão social", max_length=150)
    nome_fantasia = models.CharField("Nome fantasia", max_length=150, blank=True)
    # Guardado só com dígitos. NULL (e não "") quando vazio, para que vários
    # fornecedores sem documento não conflitem na restrição de unicidade.
    cpf_cnpj = models.CharField(
        "CPF/CNPJ", max_length=14, unique=True, null=True, blank=True, validators=[validar_cpf_cnpj]
    )
    telefone = models.CharField("Telefone", max_length=15, validators=[validar_telefone])
    email = models.EmailField("E-mail", blank=True)
    endereco = models.CharField("Endereço", max_length=255, blank=True)
    observacoes = models.TextField("Observações", blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.cpf_cnpj = somente_digitos(self.cpf_cnpj) or None
        self.telefone = somente_digitos(self.telefone)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("cadastros:fornecedor_detail", args=[self.pk])

    @property
    def cpf_cnpj_formatado(self):
        return formatar_cpf_cnpj(self.cpf_cnpj)

    @property
    def telefone_formatado(self):
        return formatar_telefone(self.telefone)
