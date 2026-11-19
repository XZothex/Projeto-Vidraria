import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from database.conexao import get_db
from decorators.permissoes import somente_administrador

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/usuarios", methods=["GET", "POST"])
@somente_administrador
def usuarios():
    db = get_db()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        username = request.form.get("username", "").strip().lower()
        senha = request.form.get("senha", "")
        tipo = request.form.get("tipo", "")
        if not nome or not username or len(senha) < 8 or tipo not in ("administrador", "funcionario"):
            flash("Preencha os campos. A senha deve ter pelo menos 8 caracteres.", "danger")
        else:
            try:
                db.execute(
                    "INSERT INTO usuarios (nome, username, senha_hash, tipo) VALUES (?, ?, ?, ?)",
                    (nome, username, generate_password_hash(senha), tipo)
                )
                db.commit()
                flash("Usuário cadastrado com sucesso.", "success")
                return redirect(url_for("admin.usuarios"))
            except sqlite3.IntegrityError:
                flash("Esse nome de usuário já está cadastrado.", "danger")
    lista = db.execute(
        "SELECT id, nome, username, tipo, ativo, criado_em FROM usuarios ORDER BY nome"
    ).fetchall()
    return render_template("admin/usuarios.html", usuarios=lista)

@admin_bp.route("/usuarios/<int:user_id>/alternar-status", methods=["POST"])
@somente_administrador
def alternar_status(user_id):
    if user_id == __import__("flask").session.get("usuario_id"):
        flash("Você não pode desativar sua própria conta.", "warning")
        return redirect(url_for("admin.usuarios"))
    db = get_db()
    db.execute("UPDATE usuarios SET ativo = 1 - ativo WHERE id = ?", (user_id,))
    db.commit()
    flash("Status do usuário atualizado.", "success")
    return redirect(url_for("admin.usuarios"))
