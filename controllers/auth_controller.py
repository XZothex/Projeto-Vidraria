from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.usuario import autenticar

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def inicio():
    return redirect(url_for("dashboard" if session.get("usuario_id") else "auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        usuario = autenticar(request.form.get("username", "").strip().lower(),
                             request.form.get("senha", ""))
        if usuario:
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["nome"] = usuario["nome"]
            session["username"] = usuario["username"]
            session["tipo"] = usuario["tipo"]
            flash(f"Bem-vindo(a), {usuario['nome']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha inválidos, ou conta desativada.", "danger")
    return render_template("login.html")

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
