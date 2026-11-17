# Módulo de pedidos e reservas

App `pedidos/` — clientes, pedidos, reserva/liberação de materiais, cancelamento e registro de entrega.

## Fluxo do pedido
```
            reservar / liberar (por item ou todos)
              ┌───────────────┐
  ABERTO ─────┴───────────────┴──► ENTREGUE   (exige todos os itens reservados; consome as reservas)
     │
     └─────────────────────────► CANCELADO   (exige motivo; libera todas as reservas)
```
- **Aberto**: itens podem ser adicionados, editados e removidos — mas só enquanto o item **não está reservado** (libere antes).
- **Entregue / Cancelado**: somente consulta. Nada é apagado.

## Modelos (`pedidos/models.py`)
| Modelo | Papel |
|---|---|
| `Cliente` | Cadastro básico (nome, CPF/CNPJ opcional e único, telefone, e-mail, endereço). Inativa, não apaga. |
| `Pedido` | Cliente, situação, entrega prevista, observações, quem criou, dados do cancelamento. |
| `ItemPedido` | Material (`PROTECT`) + quantidade + especificação (medidas, furos...). Quantidade > 0 (também no banco). |
| `Reserva` | Histórico: `ativa` → `liberada` ou `consumida`. **No máximo 1 ativa por item** (índice parcial no banco). |
| `Entrega` | 1 por pedido: data, quem recebeu, observações, quem registrou. |

Quantidade de `chapa`/`unidade` deve ser inteira; `metro`/`m²` aceitam até 3 casas decimais.

## Regras de negócio (`pedidos/services.py`)
Toda mudança de estado passa por aqui, em transação e com o pedido travado (`select_for_update`):
`reservar`, `liberar`, `cancelar`, `registrar_entrega`, `salvar_item`, `remover_item`.
Erros de regra levantam `RegraDeNegocioError` (mensagem pronta para o usuário).
- `reservar` é **tudo ou nada** e recusa material inativo.
- `registrar_entrega` exige itens e **todos reservados**; data não pode ser futura.

## ⚠️ Estoque: ponto de integração (`pedidos/estoque.py`)
Ainda não existe módulo de estoque, então **não há saldo físico**. Decisão da equipe: **o saldo será por chapa**. Hoje `saldo_fisico()` devolve `None` e as reservas
são registradas **sem checar disponibilidade**. Quando o estoque existir, implemente só `saldo_fisico(material)`:
o sistema passa a recusar reservas acima de *saldo − já reservado* (a lógica e os testes já estão prontos).

> **Atenção à unidade:** `saldo_fisico` deve devolver chapas. Isso só é comparável com materiais cujo
> `unidade_controle` é **chapa**. Materiais em **m²** ou **metro** (ex.: no `popular_cadastros`, o vidro temperado
> está em m²) precisam ser cadastrados como chapa ou convertidos antes de comparar. Combinar com quem cuida de cortes e sobras.

## Telas
`/pedidos/` (lista, busca por cliente/nº, filtro por situação) · `/pedidos/novo/` · `/pedidos/<id>/` (itens, reservas e ações) ·
`/pedidos/clientes/` (lista, cadastro, detalhe, inativar/reativar). Ações que alteram dados aceitam apenas POST.

## Executar
```bash
python manage.py migrate
python manage.py popular_cadastros   # materiais fictícios (necessário para o próximo)
python manage.py popular_pedidos     # clientes e 3 pedidos fictícios (aberto, reservado, entregue)
python manage.py test                # 69 testes
```

## Roteiro de demonstração (≈5 min)
1. **Clientes** → novo cliente (CPF inválido/duplicado dá erro) → abrir → **Novo pedido**.
2. No pedido: **Adicionar item** (tente quantidade fracionada em chapa → erro; em metro → ok).
3. **Reservar** um item e **Reservar pendentes**; tente **Editar/Remover** um item reservado (bloqueado) → **Liberar**.
4. Com um item sem reserva, note que **Registrar entrega** não aparece; reserve tudo e registre a entrega.
5. Em outro pedido: **Cancelar pedido** (motivo obrigatório) → reservas ficam “Liberado”.
6. Mostrar `pedidos/estoque.py` (integração) e o pedido entregue/cancelado somente leitura.

## Pontos a alinhar com a equipe
1. **Estoque:** quem implementa `saldo_fisico()` (saldo em chapas)? O que fazer com materiais em m²/metro?
2. **Entrega parcial:** hoje é tudo ou nada (um pedido = uma entrega).
3. **Valores/orçamento:** não há preço nos itens nem total do pedido (fora do escopo pedido).
4. **Permissões:** `pedidos/mixins.py` é o ponto único (hoje só exige login); definir quem pode cancelar/entregar.
5. **Cliente ficou no app `pedidos`** (não em `cadastros`) para não conflitar com outro módulo; mover é simples se preferirem.
6. Alterações em arquivos compartilhados: `config/settings.py` (app), `config/urls.py` (rota), `templates/base.html` (2 links no menu).
