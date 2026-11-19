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
- **Banco:** `MYSQL_*` aponta para a base SQL. Com `DB_ENGINE=mysql`, os pedidos do
  Django usam a mesma base e compartilham a transação ao reservar, liberar e entregar.
  Em SQLite ou PostgreSQL, o módulo de movimentações continua usando a conexão MySQL separada.
- **Pedidos:** em MySQL, cadastre o material com o mesmo código e unidade nos dois
  cadastros. A reserva usa lotes de compra já cadastrados. Sobras ficam fora dessa seleção.
  A entrega baixa o lote reservado ou registra quantidade zero se o lote já foi baixado
  pelo corte. Reservas antigas sem vínculo devem ser liberadas e refeitas antes da entrega.
- **Dados:** o vínculo MySQL do pedido e das reservas é criado na primeira alocação.
  Os itens SQL guardam o contexto das alocações e têm preço zero, pois o módulo de pedidos
  do Django ainda não gerencia preços. Materiais, fornecedores e logins exigem
  correspondência entre cadastros. As migrações não copiam dados de SQLite/PostgreSQL.

## Ativar a integração com pedidos

1. Em MySQL 8.4, execute `banco/mysql/sql/create_tables.sql` para criar a base. Use
   `inserts.sql` opcionalmente, uma vez, para carregar a demonstração em uma base vazia.
2. Instale `pip install -r requirements-mysql.txt`. Em Linux, se o driver for compilado,
   instale os cabeçalhos de desenvolvimento do cliente MySQL/MariaDB e o compilador.
3. Configure `DB_ENGINE=mysql` e `MYSQL_*` no `.env`. Execute `python manage.py migrate`
   para criar as tabelas Django na mesma base. Crie o usuário Django com
   `python manage.py createsuperuser`. O nome precisa existir em `usuario.login`
   no MySQL (por exemplo, `demo.estoque` no script de demonstração).
4. Cadastre no Django um material com o código e unidade de um material do estoque
   (por exemplo, `VID-T8` em chapas). Abra o pedido, reserve e confira o saldo em
   `/movimentacoes/`. Liberar devolve o disponível e entregar baixa o físico.

## Executar e testar
```bash
pip install -r requirements.txt
# no MySQL Workbench: rode banco/mysql/sql/create_tables.sql e inserts.sql
python manage.py runserver        # entre em /movimentacoes/
python manage.py test movimentacoes
```
Os testes recriam a base descartável `estoque_vidracaria_teste` com os scripts do repositório
(o usuário MySQL precisa poder criar bancos). Sem MySQL configurado, eles são pulados.
