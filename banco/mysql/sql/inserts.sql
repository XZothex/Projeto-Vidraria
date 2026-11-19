USE estoque_vidracaria_v2;

-- Execute uma vez, em uma base de demonstração recém-criada.
START TRANSACTION;
INSERT INTO fornecedor (id_fornecedor, razao_social)
VALUES (1, 'Vidros Brasil'), (2, 'Alumínios RO');

INSERT INTO cliente (id_cliente, nome)
VALUES (1, 'João Silva'), (2, 'Maria Oliveira');

INSERT INTO material (id_material, codigo, descricao, tipo, cor, espessura_mm, unidade)
VALUES (1, 'VID-T8', 'Vidro temperado 8 mm', 'vidro', 'Incolor', 8, 'chapa'),
       (2, 'PER-01', 'Perfil de alumínio', 'perfil', 'Prata', NULL, 'metro');

INSERT INTO usuario (id_usuario, nome, login, perfil)
VALUES (1, 'Operador de estoque', 'demo.estoque', 'estoque'),
       (2, 'Operador de produção', 'demo.producao', 'producao');

INSERT INTO pedido (id_pedido, id_cliente, data_pedido, status)
VALUES (1, 1, CURRENT_DATE, 'confirmado'), (2, 2, CURRENT_DATE, 'confirmado');

INSERT INTO item_pedido (id_item, id_pedido, id_material, quantidade, preco_unitario)
VALUES (1, 1, 1, 1, 350.00), (2, 2, 1, 1, 350.00);

INSERT INTO estoque (id_estoque, id_material, id_fornecedor, localizacao, largura_mm, altura_mm, custo_unitario)
VALUES (1, 1, 1, 'Galpão A', 2000, 1000, 150.00),
       (2, 2, 2, 'Galpão B', NULL, NULL, 16.50);

INSERT INTO movimentacao (id_estoque, id_usuario, tipo, quantidade, nota_fiscal)
VALUES (1, 1, 'entrada', 3, 'NF-DEMO-001'), (2, 1, 'entrada', 25.500, 'NF-DEMO-002');

INSERT INTO reserva (id_reserva, id_item, id_estoque, id_material, id_usuario, quantidade)
VALUES (1, 1, 1, 1, 1, 1), (2, 2, 1, 1, 1, 1);

-- Primeiro pedido cortado e entregue. O corte já consumiu a chapa.
UPDATE reserva SET status = 'separada' WHERE id_reserva = 1;
UPDATE reserva SET status = 'cortada' WHERE id_reserva = 1;
INSERT INTO movimentacao (id_estoque, id_reserva, id_usuario, tipo, quantidade)
VALUES (1, 1, 2, 'corte', -1);
INSERT INTO estoque (id_estoque, id_material, id_lote_origem, localizacao, origem, largura_mm, altura_mm)
VALUES (3, 1, 1, 'Prateleira de sobras', 'sobra', 800, 500);
INSERT INTO movimentacao (id_estoque, id_usuario, tipo, quantidade)
VALUES (3, 2, 'sobra', 1);
UPDATE reserva SET status = 'consumida' WHERE id_reserva = 1;
INSERT INTO movimentacao (id_estoque, id_reserva, id_usuario, tipo, quantidade)
VALUES (1, 1, 1, 'entrega', 0);
UPDATE pedido SET status = 'entregue' WHERE id_pedido = 1;
COMMIT;
