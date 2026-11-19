# Banco MySQL da vidraçaria

Atualização local do SQL de Marlon Gomes, baseada no commit `4299e71`.
Os scripts foram verificados no MySQL 8.4.

No MySQL Workbench, execute os arquivos em ordem em uma instalação com permissão
para criar bancos, tabelas, views e gatilhos:

1. `sql/create_tables.sql` cria `estoque_vidracaria_v2` e seu esquema.
2. `sql/inserts.sql` carrega uma demonstração. Execute uma vez em uma base vazia.
3. `sql/consultas.sql` mostra saldos, pedidos, histórico, sobras e reservas.

A demonstração inclui três chapas recebidas, duas reservas, um corte, uma sobra
de 800 × 500 mm e uma entrega sem nova baixa. No lote original ficam duas chapas
físicas, uma reservada e uma disponível. A sobra está em outro lote.

Os saldos do lote são mantidos pelos gatilhos de reservas e movimentações.
Registre alterações por essas tabelas e evite editar os saldos diretamente.
Faça corte e entrega em transações, seguindo a ordem de atualização do exemplo.
O roteiro diferencia entrega de material íntegro, que baixa estoque, de entrega
após corte, que registra quantidade zero. A aplicação é responsável por escolher
essa quantidade, validar as regras por unidade, limitar o total reservado por
item e conferir devoluções. Usuários são identificadores de responsáveis, sem
autenticação neste pacote.

A base `estoque_vidracaria_v2` é separada da anterior e os scripts não importam
dados de uma instalação antiga. O pacote contém apenas o banco MySQL, para
demonstração no Workbench.
