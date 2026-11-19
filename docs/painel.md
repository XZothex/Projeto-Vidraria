# Painel e relatórios

Abra **Painel** no menu após entrar no Django. O módulo reúne pedidos, reservas,
histórico de pedidos e quatro relatórios com filtros e exportação CSV.

Em `DB_ENGINE=mysql`, o relatório **Posição de estoque** lê `saldo_estoque` por
material, unidade e origem. Chapas de compra e sobras aparecem separadamente.
O painel e o relatório de reservas pendentes contabilizam apenas a parte ainda
reservada no estoque, incluindo o caso em que um dos lotes já foi cortado.
O usuário precisa ter o mesmo login no Django e em `usuario.login` do MySQL
para consultar esses dados de estoque. Em SQLite ou PostgreSQL, o relatório
de posição mostra as reservas registradas no Django.

Eventos de pedidos incluem reserva, liberação, entrega e cancelamento. O
histórico de entradas, perdas, ajustes, cortes e sobras fica em
**Estoque → Histórico**.

Veja [a configuração do MySQL](movimentacoes.md) e
[o roteiro de corte e entrega](cortes.md).
