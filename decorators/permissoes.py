from functools import wraps
from flask import session, redirect, url_for, abort, flash

def login_obrigatorio(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapper

def somente_administrador(view):
    @wraps(view)
    @login_obrigatorio
    def wrapper(*args, **kwargs):
        if session.get("tipo") != "administrador":
            abort(403)
        return view(*args, **kwargs)
    return wrapper
