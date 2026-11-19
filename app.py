import sys
from getpass import getpass
from pathlib import Path
from flask import Flask, render_template, session
from flask_wtf.csrf import CSRFProtect
from config import Config
from database.conexao import init_app, init_db
from models.usuario import criar_usuario
from controllers.auth_controller import auth_bp
from controllers.admin_controller import admin_bp
from decorators.permissoes import login_obrigatorio

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    CSRFProtect(app)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    with app.app_context():
        init_db()

    @app.route("/dashboard")
    @login_obrigatorio
    def dashboard():
        return render_template("dashboard.html")

    @app.errorhandler(403)
    def proibido(_error):
        return render_template("erros/403.html"), 403

    @app.errorhandler(404)
    def nao_encontrado(_error):
        return render_template("erros/404.html"), 404

    return app

app = create_app()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "criar-admin":
        with app.app_context():
            nome = input("Nome do administrador: ").strip()
            username = input("Usuário de acesso: ").strip().lower()
            senha = getpass("Senha (mínimo 8 caracteres): ")
            confirmacao = getpass("Confirme a senha: ")
            if not nome or not username or len(senha) < 8 or senha != confirmacao:
                print("Dados inválidos ou senhas diferentes. Administrador não criado.")
                raise SystemExit(1)
            try:
                criar_usuario(nome, username, senha, "administrador")
                print("Administrador criado com sucesso.")
            except Exception as exc:
                print(f"Não foi possível criar o administrador: {exc}")
                raise SystemExit(1)
    else:
        app.run(debug=True)
