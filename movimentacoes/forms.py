from django import forms

from cadastros.forms import BootstrapFormMixin

from . import services


def _dimensoes(lote):
    if lote["largura_mm"]:
        return f"{lote['largura_mm']}x{lote['altura_mm']} mm"
    return "sem medidas"


def rotulo_lote(lote, mostrar="fisico"):
    """Texto de um lote nos campos de seleção, ex.: '#1 VID-T8 · 2000x1000 mm · Galpão A (físico 2)'."""
    saldo = lote["fisico"] if mostrar == "fisico" else lote["disponivel"]
    nome_saldo = "físico" if mostrar == "fisico" else "disponível"
    origem = " [sobra]" if lote["origem"] == "sobra" else ""
    return (f"#{lote['id_estoque']} {lote['codigo']}{origem} · {_dimensoes(lote)} · "
            f"{lote['localizacao']} ({nome_saldo} {services.formatar_quantidade(saldo)} {lote['unidade']})")


def _escolhas(itens, valor, rotulo, vazio="---------"):
    return [("", vazio)] + [(str(i[valor]), rotulo(i)) for i in itens]


class EntradaForm(BootstrapFormMixin, forms.Form):
    id_estoque = forms.ChoiceField(
        label="Lote existente", required=False,
        help_text="Para somar em um lote que já existe. Deixe em branco para informar um material abaixo.",
    )
    id_material = forms.ChoiceField(label="Material", required=False)
    localizacao = forms.CharField(label="Localização no estoque", required=False, max_length=100)
    id_fornecedor = forms.ChoiceField(label="Fornecedor", required=False)
    largura_mm = forms.IntegerField(label="Largura (mm)", required=False, min_value=1)
    altura_mm = forms.IntegerField(label="Altura (mm)", required=False, min_value=1)
    custo_unitario = forms.CharField(label="Custo unitário (R$)", required=False, max_length=15)
    quantidade = forms.CharField(
        label="Quantidade recebida", max_length=15,
        help_text="Chapa e peça: número inteiro. Metro e m²: até 3 casas decimais.",
    )
    nota_fiscal = forms.CharField(label="Nota fiscal", max_length=60)
    motivo = forms.CharField(label="Observação", required=False, max_length=200)

    def __init__(self, *args, conn, **kwargs):
        super().__init__(*args, **kwargs)
        lotes = [l for l in services.listar_lotes(conn) if l["origem"] == "compra"]
        self.fields["id_estoque"].choices = _escolhas(lotes, "id_estoque", rotulo_lote, "— novo lote —")
        self.fields["id_material"].choices = _escolhas(
            services.listar_materiais(conn), "id_material",
            lambda m: f"{m['codigo']} — {m['descricao']} ({m['unidade']})")
        self.fields["id_fornecedor"].choices = _escolhas(
            services.listar_fornecedores(conn), "id_fornecedor", lambda f: f["razao_social"])

    def clean(self):
        dados = super().clean()
        if dados.get("id_estoque") and dados.get("id_material"):
            raise forms.ValidationError("Escolha um lote existente OU um material, não os dois.")
        if not dados.get("id_estoque") and not dados.get("id_material"):
            raise forms.ValidationError("Escolha um lote existente ou o material recebido.")
        return dados


class PerdaForm(BootstrapFormMixin, forms.Form):
    id_estoque = forms.ChoiceField(label="Lote")
    quantidade = forms.CharField(label="Quantidade perdida", max_length=15)
    categoria = forms.ChoiceField(
        label="Tipo de perda",
        choices=[("", "---------")] + [(c, c.capitalize()) for c in services.CATEGORIAS_PERDA],
    )
    motivo = forms.CharField(
        label="Motivo", max_length=180, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Conte o que aconteceu. Fica registrado no histórico, junto com a data e o responsável.",
    )

    def __init__(self, *args, conn, **kwargs):
        super().__init__(*args, **kwargs)
        lotes = [l for l in services.listar_lotes(conn) if l["disponivel"] > 0]
        self.fields["id_estoque"].choices = _escolhas(
            lotes, "id_estoque", lambda l: rotulo_lote(l, "disponivel"))
        self.fields["id_estoque"].help_text = "Só aparecem lotes com material disponível (não reservado)."


class AjusteForm(BootstrapFormMixin, forms.Form):
    id_estoque = forms.ChoiceField(label="Lote contado")
    quantidade_contada = forms.CharField(
        label="Quantidade contada (física)", max_length=15,
        help_text="O que você contou na prateleira. O sistema calcula a diferença.",
    )
    justificativa = forms.CharField(
        label="Justificativa", max_length=200, widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, conn, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id_estoque"].choices = _escolhas(services.listar_lotes(conn), "id_estoque", rotulo_lote)


class FiltroHistoricoForm(BootstrapFormMixin, forms.Form):
    tipo = forms.ChoiceField(
        label="Tipo", required=False,
        choices=[("", "Todos")] + [(t, t.capitalize()) for t in services.TIPOS_DESTE_MODULO],
    )
    id_material = forms.ChoiceField(label="Material", required=False)
    data_inicio = forms.DateField(label="De", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    data_fim = forms.DateField(label="Até", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, conn, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id_material"].choices = _escolhas(
            services.listar_materiais(conn), "id_material", lambda m: f"{m['codigo']} — {m['descricao']}", "Todos")
