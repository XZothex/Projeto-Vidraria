CREATE DATABASE IF NOT EXISTS estoque_vidracaria_v2
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE estoque_vidracaria_v2;

CREATE TABLE fornecedor (
    id_fornecedor INT AUTO_INCREMENT PRIMARY KEY,
    razao_social VARCHAR(150) NOT NULL,
    telefone VARCHAR(30),
    email VARCHAR(150)
) ENGINE=InnoDB;

CREATE TABLE cliente (
    id_cliente INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    telefone VARCHAR(30),
    email VARCHAR(150)
) ENGINE=InnoDB;

CREATE TABLE material (
    id_material INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    descricao VARCHAR(150) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    cor VARCHAR(50),
    espessura_mm DECIMAL(7,2),
    unidade ENUM('chapa', 'peca', 'metro', 'm2') NOT NULL,
    CHECK (espessura_mm IS NULL OR espessura_mm > 0)
) ENGINE=InnoDB;

CREATE TABLE usuario (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    login VARCHAR(50) NOT NULL UNIQUE,
    perfil ENUM('administracao', 'estoque', 'vendas', 'producao') NOT NULL
) ENGINE=InnoDB;

CREATE TABLE pedido (
    id_pedido INT AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT NOT NULL,
    data_pedido DATE NOT NULL,
    status ENUM('pendente', 'confirmado', 'entregue', 'cancelado') NOT NULL DEFAULT 'pendente',
    FOREIGN KEY (id_cliente) REFERENCES cliente (id_cliente)
) ENGINE=InnoDB;

CREATE TABLE item_pedido (
    id_item INT AUTO_INCREMENT PRIMARY KEY,
    id_pedido INT NOT NULL,
    id_material INT NOT NULL,
    quantidade DECIMAL(12,3) NOT NULL CHECK (quantidade > 0),
    preco_unitario DECIMAL(12,2) NOT NULL CHECK (preco_unitario >= 0),
    UNIQUE (id_item, id_material),
    FOREIGN KEY (id_pedido) REFERENCES pedido (id_pedido),
    FOREIGN KEY (id_material) REFERENCES material (id_material)
) ENGINE=InnoDB;

CREATE TABLE estoque (
    id_estoque INT AUTO_INCREMENT PRIMARY KEY,
    id_material INT NOT NULL,
    id_fornecedor INT,
    id_lote_origem INT,
    localizacao VARCHAR(100) NOT NULL,
    origem ENUM('compra', 'sobra') NOT NULL DEFAULT 'compra',
    largura_mm INT,
    altura_mm INT,
    custo_unitario DECIMAL(12,2) CHECK (custo_unitario >= 0),
    saldo_fisico DECIMAL(15,3) NOT NULL DEFAULT 0,
    saldo_reservado DECIMAL(15,3) NOT NULL DEFAULT 0,
    CHECK (saldo_fisico >= saldo_reservado AND saldo_reservado >= 0),
    UNIQUE (id_estoque, id_material),
    FOREIGN KEY (id_material) REFERENCES material (id_material),
    FOREIGN KEY (id_fornecedor) REFERENCES fornecedor (id_fornecedor),
    FOREIGN KEY (id_lote_origem, id_material) REFERENCES estoque (id_estoque, id_material),
    CHECK (origem <> 'sobra' OR (id_lote_origem IS NOT NULL AND largura_mm IS NOT NULL)),
    CHECK ((largura_mm IS NULL AND altura_mm IS NULL)
        OR (largura_mm IS NOT NULL AND altura_mm IS NOT NULL AND largura_mm > 0 AND altura_mm > 0))
) ENGINE=InnoDB;

CREATE TABLE reserva (
    id_reserva INT AUTO_INCREMENT PRIMARY KEY,
    id_item INT NOT NULL,
    id_estoque INT NOT NULL,
    id_material INT NOT NULL,
    id_usuario INT NOT NULL,
    quantidade DECIMAL(12,3) NOT NULL CHECK (quantidade > 0),
    status ENUM('ativa', 'separada', 'cortada', 'liberada', 'consumida') NOT NULL DEFAULT 'ativa',
    criada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_item, id_material) REFERENCES item_pedido (id_item, id_material),
    FOREIGN KEY (id_estoque, id_material) REFERENCES estoque (id_estoque, id_material),
    FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario),
    UNIQUE (id_reserva, id_estoque)
) ENGINE=InnoDB;

CREATE TABLE movimentacao (
    id_movimentacao INT AUTO_INCREMENT PRIMARY KEY,
    id_estoque INT NOT NULL,
    id_reserva INT,
    id_usuario INT NOT NULL,
    data_movimentacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo ENUM('entrada', 'corte', 'sobra', 'perda', 'entrega', 'devolucao', 'ajuste') NOT NULL,
    quantidade DECIMAL(12,3) NOT NULL,
    nota_fiscal VARCHAR(60),
    motivo VARCHAR(200),
    etapa_unica VARCHAR(10) GENERATED ALWAYS AS (
        CASE WHEN tipo IN ('corte', 'entrega') THEN tipo ELSE NULL END
    ) STORED,
    UNIQUE (id_reserva, etapa_unica),
    FOREIGN KEY (id_estoque) REFERENCES estoque (id_estoque),
    FOREIGN KEY (id_reserva, id_estoque) REFERENCES reserva (id_reserva, id_estoque),
    FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario),
    CHECK ((tipo IN ('entrada', 'sobra', 'devolucao') AND quantidade > 0)
        OR (tipo IN ('corte', 'perda') AND quantidade < 0)
        OR (tipo = 'entrega' AND quantidade <= 0)
        OR (tipo = 'ajuste' AND quantidade <> 0)),
    CHECK (tipo NOT IN ('perda', 'ajuste') OR (motivo IS NOT NULL AND CHAR_LENGTH(TRIM(motivo)) > 0)),
    CHECK (tipo NOT IN ('corte', 'entrega', 'devolucao') OR id_reserva IS NOT NULL),
    INDEX ix_movimentacao_data (data_movimentacao, id_movimentacao)
) ENGINE=InnoDB;

-- Operações de reserva e saldo serializam pelo lote no InnoDB.
DELIMITER //
CREATE TRIGGER reserva_inserir AFTER INSERT ON reserva FOR EACH ROW
BEGIN
    IF NEW.status NOT IN ('ativa', 'separada') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A reserva deve iniciar ativa ou separada';
    END IF;
    UPDATE estoque SET saldo_reservado = saldo_reservado + NEW.quantidade
    WHERE id_estoque = NEW.id_estoque;
END//

CREATE TRIGGER reserva_atualizar AFTER UPDATE ON reserva FOR EACH ROW
BEGIN
    IF NEW.id_reserva <> OLD.id_reserva OR NEW.id_item <> OLD.id_item
       OR NEW.id_estoque <> OLD.id_estoque OR NEW.id_material <> OLD.id_material
       OR NEW.id_usuario <> OLD.id_usuario OR NEW.quantidade <> OLD.quantidade
       OR NEW.criada_em <> OLD.criada_em THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Altere somente o estado da reserva';
    END IF;
    IF NEW.status <> OLD.status THEN
        IF OLD.status IN ('ativa', 'separada') AND NEW.status IN ('cortada', 'liberada', 'consumida') THEN
            UPDATE estoque SET saldo_reservado = saldo_reservado - OLD.quantidade
            WHERE id_estoque = OLD.id_estoque;
        ELSEIF NOT ((OLD.status = 'ativa' AND NEW.status = 'separada')
                 OR (OLD.status = 'cortada' AND NEW.status = 'consumida')) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Transição de reserva inválida';
        END IF;
    END IF;
END//

CREATE TRIGGER reserva_excluir BEFORE DELETE ON reserva FOR EACH ROW
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Preserve a reserva no histórico'//

CREATE TRIGGER movimentacao_inserir AFTER INSERT ON movimentacao FOR EACH ROW
    UPDATE estoque SET saldo_fisico = saldo_fisico + NEW.quantidade
    WHERE id_estoque = NEW.id_estoque//

CREATE TRIGGER movimentacao_atualizar BEFORE UPDATE ON movimentacao FOR EACH ROW
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Use um ajuste para corrigir a movimentação'//

CREATE TRIGGER movimentacao_excluir BEFORE DELETE ON movimentacao FOR EACH ROW
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Use um ajuste para corrigir a movimentação'//
DELIMITER ;

CREATE VIEW saldo_estoque AS
SELECT e.id_estoque, e.id_material, m.codigo, m.descricao, m.unidade, e.localizacao,
       e.origem, e.largura_mm, e.altura_mm,
       CAST(e.largura_mm AS DECIMAL(20,6)) * e.altura_mm / 1000000 AS area_unitaria_m2,
       e.saldo_fisico AS fisico, e.saldo_reservado AS reservado,
       e.saldo_fisico - e.saldo_reservado AS disponivel
FROM estoque AS e
JOIN material AS m ON m.id_material = e.id_material;

CREATE VIEW total_pedido AS
SELECT p.id_pedido, p.id_cliente, p.status,
       COALESCE(SUM(ROUND(i.quantidade * i.preco_unitario, 2)), 0) AS valor_total
FROM pedido AS p
LEFT JOIN item_pedido AS i ON i.id_pedido = p.id_pedido
GROUP BY p.id_pedido, p.id_cliente, p.status;
