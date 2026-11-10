"""Configurações do projeto Vidraria.

Valores sensíveis vêm de variáveis de ambiente (arquivo .env, ignorado pelo Git).
Veja o .env.example.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(nome, padrao=False):
    return os.environ.get(nome, str(padrao)).strip().lower() in {"1", "true", "yes", "sim"}


DEBUG = _bool("DJANGO_DEBUG", True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # Chave descartável, apenas para desenvolvimento local.
        SECRET_KEY = "dev-inseguro-apenas-para-desenvolvimento-local"
    else:
        raise RuntimeError("Defina DJANGO_SECRET_KEY quando DJANGO_DEBUG=False.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",  # autenticação padrão do Django (não criamos outro modelo de usuário)
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Módulos do sistema (um app por responsabilidade)
    "cadastros",  # materiais e fornecedores
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Banco de dados -------------------------------------------------------
# SQLite = apenas desenvolvimento local. PostgreSQL = banco definitivo.
if os.environ.get("DB_ENGINE", "sqlite").lower() == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "vidraria"),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Autenticação (PONTO DE INTEGRAÇÃO) -------------------------------------
# Enquanto o módulo de login não existir, usamos o LoginView padrão do Django
# (config/urls.py). Quando o módulo de login/permissões estiver pronto, basta
# ajustar LOGIN_URL e as rotas; as views de cadastros só dependem do mixin
# cadastros.mixins.AcessoCadastrosMixin.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "cadastros:material_list"
LOGOUT_REDIRECT_URL = "login"

# --- Idioma e fuso ---------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
