from werkzeug.security import generate_password_hash, check_password_hash
from database.conexao import get_db

def buscar_por_username(username):
    return get_db().execute(
        "SELECT * FROM usuarios WHERE username = ?", (username,)
    ).fetchone()

def autenticar(username, senha):
    usuario = buscar_por_username(username)
    if usuario is None or not usuario["ativo"]:
        return None
    if not check_password_hash(usuario["senha_hash"], senha):
        return None
    return usuario

def criar_usuario(nome, username, senha, tipo):
    if tipo not in ("administrador", "funcionario"):
        raise ValueError("Tipo de usuário inválido.")
    db = get_db()
    db.execute(
        "INSERT INTO usuarios (nome, username, senha_hash, tipo) VALUES (?, ?, ?, ?)",
        (nome.strip(), username.strip().lower(), generate_password_hash(senha), tipo)
    )
    db.commit()
