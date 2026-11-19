"""Regras de negócio de pedidos e reservas.

Toda alteração de estado passa por aqui (as views só chamam estas funções), dentro de
``transaction.atomic`` e com o pedido travado (``select_for_update``) para evitar que
dois usuários reservem/cancelem/entreguem o mesmo pedido ao mesmo tempo. Erros de regra
viram ``RegraDeNegocioError`` com mensagem pronta para mostrar ao usuário.
"""
from collections import defaultdict
from decimal import Decimal

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from cadastros.models import Material

from . import estoque, estoque_mysql
from .models import Entrega, ItemPedido, Pedido, Reserva


class RegraDeNegocioError(Exception):
    """Operação recusada por uma regra de negócio (mensagem amigável)."""


def _operacao_mysql(operacao, *args, **kwargs):
    try:
        return operacao(*args, **kwargs)
    except estoque_mysql.ErroEstoque as exc:
        raise RegraDeNegocioError(str(exc)) from exc
    except IntegrityError as exc:
        raise RegraDeNegocioError("O estoque MySQL recusou a operação. Confira o saldo e a reserva.") from exc
    except OperationalError as exc:
        if exc.args and exc.args[0] in (1205, 1213):
            raise RegraDeNegocioError("O estoque está ocupado. Tente a operação novamente.") from exc
        raise


def _fmt(qtd):
    return f"{Decimal(qtd).normalize():f}"


def _pedido_aberto_travado(pedido):
    """Relê o pedido com trava e garante que ainda está aberto."""
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if not pedido.aberto:
        raise RegraDeNegocioError(
            f"O {pedido} está {pedido.get_status_display().lower()} e não pode mais ser alterado."
        )
    return pedido


def _itens_do_pedido(pedido, itens):
    """Itens a tratar: todos do pedido ou só os informados (que devem ser do pedido)."""
    qs = pedido.itens.select_related("material").order_by("pk")
    if itens is not None:
        ids = [i.pk for i in itens]
        qs = qs.filter(pk__in=ids)
        if qs.count() != len(set(ids)):
            raise RegraDeNegocioError("Item não pertence a este pedido.")
    return list(qs)


# ----------------------------- Itens ---------------------------------------
@transaction.atomic
def salvar_item(item):
    """Grava (cria ou altera) um item. Só em pedido aberto e item sem reserva ativa."""
    _pedido_aberto_travado(item.pedido)
    if item.pk and item.reservas.filter(status=Reserva.Status.ATIVA).exists():
        raise RegraDeNegocioError("Libere a reserva do item antes de alterá-lo.")
    if not item.material.ativo:
        # Item antigo com material depois inativado pode ser editado; escolher um inativo, não.
        material_original = (
            ItemPedido.objects.filter(pk=item.pk).values_list("material_id", flat=True).first() if item.pk else None
        )
        if material_original != item.material_id:
            raise RegraDeNegocioError("Este material está inativo.")
    item.save()
    return item


@transaction.atomic
def remover_item(item):
    _pedido_aberto_travado(item.pedido)
    if item.reservas.filter(status=Reserva.Status.ATIVA).exists():
        raise RegraDeNegocioError("Libere a reserva do item antes de removê-lo.")
    item.delete()


# ------------------------- Reserva e liberação ------------------------------
@transaction.atomic
def reservar(pedido, usuario, itens=None):
    """Reserva os itens ainda não reservados (todos, ou só os informados).

    Tudo ou nada: se algum material não tiver disponibilidade, nada é reservado.
    """
    pedido = _pedido_aberto_travado(pedido)
    pendentes = [i for i in _itens_do_pedido(pedido, itens) if not i.reservas.filter(status=Reserva.Status.ATIVA).exists()]
    if not pendentes:
        raise RegraDeNegocioError("Não há itens pendentes de reserva.")

    inativos = sorted({i.material.codigo for i in pendentes if not i.material.ativo})
    if inativos:
        raise RegraDeNegocioError("Material inativo, não é possível reservar: " + ", ".join(inativos) + ".")

    # Trava os materiais em ordem fixa (evita deadlock) antes de conferir a disponibilidade.
    ids_materiais = sorted({i.material_id for i in pendentes})
    materiais = {m.pk: m for m in Material.objects.select_for_update().filter(pk__in=ids_materiais).order_by("pk")}
    if estoque_mysql.ativo():
        alocacoes = _operacao_mysql(estoque_mysql.reservar, pedido, pendentes, usuario)
        Reserva.objects.bulk_create([
            Reserva(item=item, quantidade=item.quantidade, criada_por=usuario, mysql_reservas=ids)
            for item, ids in zip(pendentes, alocacoes, strict=True)
        ])
        return len(pendentes)

    necessario = defaultdict(Decimal)
    for item in pendentes:
        necessario[item.material_id] += item.quantidade
    faltas = []
    for material_id, qtd in necessario.items():
        material = materiais[material_id]
        disponivel = estoque.quantidade_disponivel(material)
        if disponivel is not None and qtd > disponivel:
            faltas.append(
                f"{material.codigo}: necessário {_fmt(qtd)}, disponível {_fmt(max(disponivel, Decimal('0')))} "
                f"({material.get_unidade_controle_display().lower()})"
            )
    if faltas:
        raise RegraDeNegocioError("Disponibilidade insuficiente — " + "; ".join(faltas) + ".")

    Reserva.objects.bulk_create(
        [Reserva(item=i, quantidade=i.quantidade, criada_por=usuario) for i in pendentes]
    )
    return len(pendentes)


@transaction.atomic
def liberar(pedido, usuario, itens=None):
    """Libera as reservas ativas (todas, ou só dos itens informados)."""
    pedido = _pedido_aberto_travado(pedido)
    ids = [i.pk for i in _itens_do_pedido(pedido, itens)]
    ativas = Reserva.objects.filter(item_id__in=ids, status=Reserva.Status.ATIVA)
    if estoque_mysql.ativo():
        _operacao_mysql(estoque_mysql.encerrar, list(ativas), usuario)
    quantidade = ativas.update(
        status=Reserva.Status.LIBERADA, encerrada_em=timezone.now(), encerrada_por=usuario
    )
    if not quantidade:
        raise RegraDeNegocioError("Não há reservas ativas para liberar.")
    return quantidade


# ------------------------ Cancelamento e entrega ----------------------------
@transaction.atomic
def cancelar(pedido, usuario, motivo):
    """Cancela o pedido aberto e libera todas as reservas ativas."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise RegraDeNegocioError("Informe o motivo do cancelamento.")
    pedido = _pedido_aberto_travado(pedido)
    agora = timezone.now()
    ativas = Reserva.objects.filter(item__pedido=pedido, status=Reserva.Status.ATIVA)
    if estoque_mysql.ativo():
        _operacao_mysql(estoque_mysql.encerrar, list(ativas), usuario)
        _operacao_mysql(estoque_mysql.atualizar_pedido, pedido, "cancelado")
    ativas.update(
        status=Reserva.Status.LIBERADA, encerrada_em=agora, encerrada_por=usuario
    )
    pedido.status = Pedido.Status.CANCELADO
    pedido.cancelado_em = agora
    pedido.cancelado_por = usuario
    pedido.motivo_cancelamento = motivo
    pedido.save()
    return pedido


@transaction.atomic
def registrar_entrega(pedido, usuario, data_entrega, recebido_por, observacoes=""):
    """Registra a entrega: consome as reservas e encerra o pedido.

    Exige que o pedido tenha itens e que todos estejam reservados (o que sai deve ter
    sido separado).
    """
    pedido = _pedido_aberto_travado(pedido)
    itens = list(pedido.itens.all())
    if not itens:
        raise RegraDeNegocioError("O pedido não tem itens.")
    sem_reserva = [i for i in itens if not i.reservas.filter(status=Reserva.Status.ATIVA).exists()]
    if sem_reserva:
        raise RegraDeNegocioError(
            f"Reserve todos os itens antes de entregar ({len(sem_reserva)} sem reserva)."
        )
    if data_entrega > timezone.localdate():
        raise RegraDeNegocioError("A data da entrega não pode ser futura.")
    ativas = Reserva.objects.filter(item__pedido=pedido, status=Reserva.Status.ATIVA)
    if estoque_mysql.ativo():
        _operacao_mysql(estoque_mysql.encerrar, list(ativas), usuario, entrega=True)
        _operacao_mysql(estoque_mysql.atualizar_pedido, pedido, "entregue")
    ativas.update(
        status=Reserva.Status.CONSUMIDA, encerrada_em=timezone.now(), encerrada_por=usuario
    )
    Entrega.objects.create(
        pedido=pedido, data_entrega=data_entrega, recebido_por=recebido_por.strip(),
        observacoes=observacoes, registrado_por=usuario,
    )
    pedido.status = Pedido.Status.ENTREGUE
    pedido.save()
    return pedido
