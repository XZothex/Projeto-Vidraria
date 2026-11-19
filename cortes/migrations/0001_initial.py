# Generated for the independent cortes app.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cadastros", "0002_material_material_espessura_positiva"),
        ("pedidos", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="ChapaDisponivel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("chapa", "Chapa inteira"), ("sobra", "Sobra reaproveitável")], default="chapa", max_length=10)),
                ("largura_mm", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Largura (mm)")),
                ("altura_mm", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Altura (mm)")),
                ("espessura_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name="Espessura (mm)")),
                ("codigo", models.CharField(blank=True, db_index=True, max_length=40, verbose_name="Identificação")),
                ("origem_descricao", models.CharField(blank=True, max_length=180, verbose_name="Origem / observação")),
                ("status", models.CharField(choices=[("disponivel", "Disponível"), ("reservada", "Reservada"), ("consumida", "Consumida"), ("inativa", "Inativa")], db_index=True, default="disponivel", max_length=12)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="chapas_corte", to="cadastros.material")),
                ("sobra_de", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sobras_geradas", to="cortes.chapadisponivel")),
            ],
            options={"ordering": ["material__nome", "-criado_em"]},
        ),
        migrations.CreateModel(
            name="OperacaoCorte",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origem", models.CharField(choices=[("estoque", "Chapa/sobra cadastrada no estoque"), ("manual", "Informar chapa manualmente")], max_length=10)),
                ("largura_chapa_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Largura da chapa (mm)")),
                ("altura_chapa_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Altura da chapa (mm)")),
                ("espessura_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name="Espessura (mm)")),
                ("quantidade_chapas", models.PositiveIntegerField(default=1, verbose_name="Quantidade de chapas")),
                ("kerf_mm", models.DecimalField(decimal_places=2, default=__import__('decimal').Decimal('3.00'), max_digits=5, verbose_name="Perda por corte (mm)")),
                ("observacoes", models.TextField(blank=True)),
                ("realizado_em", models.DateTimeField(auto_now_add=True)),
                ("chapa_estoque", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operacoes_corte", to="cortes.chapadisponivel")),
                ("item_pedido", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operacoes_corte", to="pedidos.itempedido")),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operacoes_corte", to="cadastros.material")),
                ("pedido", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operacoes_corte", to="pedidos.pedido")),
                ("realizado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cortes_realizados", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-realizado_em", "-pk"]},
        ),
        migrations.CreateModel(
            name="PecaCortada",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificacao", models.CharField(blank=True, max_length=100, verbose_name="Identificação da peça")),
                ("largura_mm", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Largura (mm)")),
                ("altura_mm", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Altura (mm)")),
                ("quantidade", models.PositiveIntegerField(default=1)),
                ("operacao", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pecas", to="cortes.operacaocorte")),
            ],
        ),
        migrations.CreateModel(
            name="Sobra",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("largura_mm", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Largura (mm)")),
                ("altura_mm", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Altura (mm)")),
                ("status", models.CharField(choices=[("disponivel", "Disponível"), ("reservada", "Reservada"), ("utilizada", "Utilizada"), ("descartada", "Descartada")], default="disponivel", max_length=12)),
                ("observacoes", models.CharField(blank=True, max_length=180)),
                ("chapa_gerada", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="registro_sobra", to="cortes.chapadisponivel")),
                ("operacao", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sobras", to="cortes.operacaocorte")),
            ],
        ),
        migrations.AddConstraint(model_name="chapadisponivel", constraint=models.CheckConstraint(condition=models.Q(("largura_mm__gt", 0)), name="chapa_largura_positiva")),
        migrations.AddConstraint(model_name="chapadisponivel", constraint=models.CheckConstraint(condition=models.Q(("altura_mm__gt", 0)), name="chapa_altura_positiva")),
        migrations.AddConstraint(model_name="chapadisponivel", constraint=models.CheckConstraint(condition=models.Q(("espessura_mm__isnull", True), ("espessura_mm__gt", 0), _connector="OR"), name="chapa_espessura_positiva")),
        migrations.AddConstraint(model_name="operacaocorte", constraint=models.CheckConstraint(condition=models.Q(("largura_chapa_mm__gt", 0)), name="corte_largura_positiva")),
        migrations.AddConstraint(model_name="operacaocorte", constraint=models.CheckConstraint(condition=models.Q(("altura_chapa_mm__gt", 0)), name="corte_altura_positiva")),
        migrations.AddConstraint(model_name="operacaocorte", constraint=models.CheckConstraint(condition=models.Q(("quantidade_chapas__gt", 0)), name="corte_qtd_chapas_positiva")),
        migrations.AddConstraint(model_name="operacaocorte", constraint=models.CheckConstraint(condition=models.Q(("kerf_mm__gte", 0)), name="corte_kerf_nao_negativo")),
        migrations.AddConstraint(model_name="pecacortada", constraint=models.CheckConstraint(condition=models.Q(("largura_mm__gt", 0)), name="peca_largura_positiva")),
        migrations.AddConstraint(model_name="pecacortada", constraint=models.CheckConstraint(condition=models.Q(("altura_mm__gt", 0)), name="peca_altura_positiva")),
        migrations.AddConstraint(model_name="pecacortada", constraint=models.CheckConstraint(condition=models.Q(("quantidade__gt", 0)), name="peca_qtd_positiva")),
        migrations.AddConstraint(model_name="sobra", constraint=models.CheckConstraint(condition=models.Q(("largura_mm__gt", 0)), name="sobra_largura_positiva")),
        migrations.AddConstraint(model_name="sobra", constraint=models.CheckConstraint(condition=models.Q(("altura_mm__gt", 0)), name="sobra_altura_positiva")),
    ]
