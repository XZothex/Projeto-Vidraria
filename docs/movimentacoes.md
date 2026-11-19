# Módulo de entradas, perdas e ajustes (`movimentacoes/`)

Registra recebimentos, quebras/defeitos/extravios e ajustes de inventário no banco MySQL
`estoque_vidracaria_v2` (`banco/mysql`). Mostra também o saldo por lote e o histórico.

## Telas
| Rota | O que faz | Quem acessa |
|---|---|---|
| `/movimentacoes/` | Saldo físico, reservado e disponível de cada lote (busca por código, descrição ou local) | todos |
| `/movimentacoes/historico/` | Histórico de entradas, perdas e ajustes (filtros: tipo, material, período) | todos |
| `/movimentacoes/entrada/` | Recebimento com nota fiscal, em lote existente ou lote novo | administracao, estoque |
| `/movimentacoes/perda/` | Quebra, defeito ou extravio, com motivo obrigatório | administracao, estoque, producao |
| `/movimentacoes/ajuste/` | Ajuste pela contagem física, com justificativa | administracao |

Quem manda em quem pode o quê são as constantes `PERFIS_*` em `movimentacoes/services.py`.

## Regras (`services.py`)
- O saldo nunca é alterado direto: tudo é um INSERT em `movimentacao`, e os gatilhos do banco somam em `estoque.saldo_fisico`.
- Perda só do que está **disponível** (físico − reservado). Ajuste não pode deixar o físico abaixo do reservado.
- Chapa e peça: quantidade inteira. Metro e m²: até 3 casas. Chapa nova exige largura e altura em mm.
- Entrada em lote novo reaproveita um lote de compra idêntico (material, fornecedor, medidas, local e custo).
- O banco não tem coluna de categoria da perda: ela vai no início do motivo (`Quebra: ...`).
- Movimentações não são editadas nem apagadas (os gatilhos impedem). Para corrigir, faça um ajuste.
- Cada operação trava o lote (`SELECT ... FOR UPDATE`) e roda em transação.

## Pontos de integração
- **Usuário:** o login do Django (`username`) deve ser igual a `usuario.login` no MySQL, que traz o `perfil`.
  A ligação fica em `AcessoMovimentacoesMixin.buscar_usuario` (`mixins.py`); trocar lá quando o módulo de login decidir outra forma.
- **Banco:** conexão pelas variáveis `MYSQL_*` do `.env` (veja `.env.example`). O resto do projeto continua em SQLite/PostgreSQL.
- **Pedidos:** `pedidos/estoque.py::saldo_fisico` ainda devolve `None`. A consulta pronta é `services.listar_lotes` (coluna `disponivel`),
  mas só vale a pena ligar depois que o grupo decidir qual banco será o definitivo.

## Executar e testar
```bash
pip install -r requirements.txt
# no MySQL Workbench: rode banco/mysql/sql/create_tables.sql e inserts.sql
python manage.py runserver        # entre em /movimentacoes/
python manage.py test movimentacoes
```
Os testes recriam a base descartável `estoque_vidracaria_teste` com os scripts do repositório
(o usuário MySQL precisa poder criar bancos). Sem MySQL configurado, eles são pulados.
