USE estoque_vidracaria_v2;

-- Saldo físico, reservado e disponível por lote e unidade.
SELECT id_estoque, codigo, descricao, unidade, origem, localizacao,
       largura_mm, altura_mm, ROUND(area_unitaria_m2, 6) AS area_unitaria_m2,
       fisico, reservado, disponivel
FROM saldo_estoque
ORDER BY id_estoque;

-- Pedidos, clientes e valor calculado a partir dos itens.
SELECT p.id_pedido, c.nome AS cliente, p.status, p.valor_total
FROM total_pedido AS p
JOIN cliente AS c ON c.id_cliente = p.id_cliente
ORDER BY p.id_pedido;

-- Histórico com lote, material, fornecedor, responsável e pedido quando vinculado.
SELECT mov.id_movimentacao, mov.data_movimentacao, mov.tipo, m.codigo, m.unidade,
       mov.quantidade, mov.id_estoque, f.razao_social AS fornecedor, i.id_pedido,
       u.nome AS responsavel, mov.nota_fiscal, mov.motivo
FROM movimentacao AS mov
JOIN estoque AS e ON e.id_estoque = mov.id_estoque
JOIN material AS m ON m.id_material = e.id_material
JOIN usuario AS u ON u.id_usuario = mov.id_usuario
LEFT JOIN fornecedor AS f ON f.id_fornecedor = e.id_fornecedor
LEFT JOIN reserva AS r ON r.id_reserva = mov.id_reserva
LEFT JOIN item_pedido AS i ON i.id_item = r.id_item
ORDER BY mov.data_movimentacao, mov.id_movimentacao;

-- Sobras disponíveis para reaproveitamento, com suas próprias dimensões.
SELECT codigo, localizacao, largura_mm, altura_mm, disponivel
FROM saldo_estoque
WHERE origem = 'sobra' AND disponivel > 0
ORDER BY codigo, id_estoque;

-- Reservas em aberto.
SELECT i.id_pedido, r.id_estoque, m.codigo, m.unidade, r.quantidade, r.status, r.criada_em
FROM reserva AS r
JOIN item_pedido AS i ON i.id_item = r.id_item
JOIN material AS m ON m.id_material = r.id_material
WHERE r.status IN ('ativa', 'separada', 'cortada')
ORDER BY r.criada_em, r.id_reserva;
