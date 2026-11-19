# Etapa 6 — Cortes e sobras

O módulo registra o corte, as peças produzidas, as sobras e o responsável.
Use **Cortes e sobras** no menu do Django após executar `python manage.py migrate`.

## Demonstração com MySQL

1. Configure o projeto conforme o [guia de movimentações](movimentacoes.md).
2. Cadastre um material controlado por chapa com o mesmo código no Django e no MySQL.
3. Registre a entrada de chapas com largura e altura. Abra um pedido com esse material e reserve.
4. Em **Cortes e sobras**, registre o corte com a origem **Lote reservado no MySQL**.
   Informe as peças e as sobras. Use milímetros inteiros nas dimensões das sobras.
5. Confira o saldo e os lotes de sobras em **Estoque**. Conclua a entrega em **Pedidos**.

Cada corte MySQL exige uma reserva ativa em um único lote e consome a quantidade
reservada inteira. A baixa do lote, a entrada das sobras e o registro da operação
ocorrem na mesma transação. A entrega após o corte registra quantidade zero.
O acesso de escrita exige um login vinculado aos perfis administração, estoque ou
produção. Sobras aparecem como lotes separados no MySQL e a reserva de pedidos continua
selecionando chapas de compra. O reaproveitamento automático de sobras em pedidos
MySQL fica para uma etapa futura.

## Demonstração local

Com SQLite ou PostgreSQL, o módulo usa o próprio cadastro de chapas. Você pode
selecionar uma chapa cadastrada ou informar suas dimensões manualmente. As sobras
geradas aparecem em **Chapas e sobras** e podem ser selecionadas em cortes futuros.
Esse estoque local é separado do saldo exibido pelo módulo de movimentações.

A validação confere dimensões individuais e compara as áreas de peças, sobras e a
perda estimada da serra com a área total das chapas. A disposição das peças deve
ser conferida pelo operador.

## Verificação

Execute `python manage.py test cortes` para os testes do módulo com SQLite. Para
verificar o fluxo integrado em um banco de testes MySQL, configure `DB_ENGINE=mysql`
e execute `python manage.py test pedidos.tests.test_estoque_mysql`.
