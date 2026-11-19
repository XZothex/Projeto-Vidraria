from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from pedidos.models import ItemPedido, Pedido
from . import estoque_mysql
from .models import ChapaDisponivel, OperacaoCorte, PecaCortada, Sobra


@transaction.atomic
def registrar_operacao(*, operacao, pecas, sobras, usuario=None, id_reserva_mysql=None):
    """Registra o corte, consome a chapa selecionada e cria sobras no estoque.

    Validação por área é um controle preliminar: não substitui um algoritmo de
    plano de corte/encaixe geométrico. A equipe pode evoluir essa regra depois.
    """
    pedido = Pedido.objects.select_for_update().get(pk=operacao.pedido_id)
    if not pedido.aberto:
        raise ValidationError("O pedido precisa estar aberto para registrar um corte.")
    try:
        operacao.item_pedido = ItemPedido.objects.get(pk=operacao.item_pedido_id, pedido=pedido)
    except ItemPedido.DoesNotExist as exc:
        raise ValidationError("O item não pertence mais ao pedido.") from exc
    operacao.realizado_por = usuario
    alocacao = None
    origem_mysql = operacao.origem == OperacaoCorte.Origem.MYSQL
    if (connection.vendor == "mysql") != origem_mysql:
        raise ValidationError("Selecione a origem de estoque correspondente ao banco em uso.")
    if origem_mysql:
        if usuario is None:
            raise ValidationError("Informe o responsável pelo corte.")
        with connection.cursor() as cursor:
            alocacao = estoque_mysql.preparar(cursor, operacao, usuario, id_reserva_mysql)
    if operacao.origem == OperacaoCorte.Origem.ESTOQUE:
        chapa = ChapaDisponivel.objects.select_for_update().get(pk=operacao.chapa_estoque_id)
        if chapa.status != ChapaDisponivel.Status.DISPONIVEL:
            raise ValidationError("A chapa deixou de estar disponível. Atualize a página e tente novamente.")
        operacao.chapa_estoque = chapa
        operacao.largura_chapa_mm = chapa.largura_mm
        operacao.altura_chapa_mm = chapa.altura_mm
        operacao.espessura_mm = chapa.espessura_mm
    else:
        chapa = None
    operacao.full_clean()

    area_disponivel = operacao.largura_chapa_mm * operacao.altura_chapa_mm * operacao.quantidade_chapas
    area_pecas = sum((p["largura_mm"] * p["altura_mm"] * p["quantidade"] for p in pecas), Decimal("0"))
    area_sobras = sum((s["largura_mm"] * s["altura_mm"] for s in sobras), Decimal("0"))
    if not pecas:
        raise ValidationError("Informe pelo menos uma peça produzida.")
    for p in pecas:
        if p["largura_mm"] > operacao.largura_chapa_mm or p["altura_mm"] > operacao.altura_chapa_mm:
            raise ValidationError("As dimensões de uma peça não podem ultrapassar as dimensões da chapa.")
    for s in sobras:
        if s["largura_mm"] > operacao.largura_chapa_mm or s["altura_mm"] > operacao.altura_chapa_mm:
            raise ValidationError("As dimensões de uma sobra não podem ultrapassar as dimensões da chapa.")
    # Reserva de área conservadora para a perda da serra/disco: perímetro de peças * kerf.
    perimetro_total = sum(((p["largura_mm"] + p["altura_mm"]) * 2 * p["quantidade"] for p in pecas), Decimal("0"))
    area_kerf = perimetro_total * operacao.kerf_mm
    if area_pecas + area_sobras + area_kerf > area_disponivel:
        raise ValidationError("A área das peças, sobras e perdas estimadas excede a área total das chapas informadas.")

    operacao.save()
    if chapa:
        chapa.status = ChapaDisponivel.Status.CONSUMIDA
        chapa.save(update_fields=["status"])
        # Mantém o status do registro histórico da sobra sincronizado.
        Sobra.objects.filter(chapa_gerada=chapa).update(status=Sobra.Status.UTILIZADA)
    for p in pecas:
        PecaCortada.objects.create(operacao=operacao, **p)
    if alocacao is not None:
        ids = estoque_mysql.baixar(alocacao, sobras)
        for dados, id_lote in zip(sobras, ids, strict=True):
            Sobra.objects.create(operacao=operacao, mysql_lote_id=id_lote, **dados)
        return operacao
    for s in sobras:
        nova_chapa = ChapaDisponivel.objects.create(
            material=operacao.material, tipo=ChapaDisponivel.Tipo.SOBRA,
            largura_mm=s["largura_mm"], altura_mm=s["altura_mm"],
            espessura_mm=operacao.espessura_mm, sobra_de=chapa,
            origem_descricao=f"Sobra gerada no corte #{operacao.pk}",
        )
        Sobra.objects.create(operacao=operacao, chapa_gerada=nova_chapa, **s)
    return operacao
