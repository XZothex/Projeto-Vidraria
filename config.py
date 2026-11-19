import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "TROQUE-ESTA-CHAVE-EM-PRODUCAO")
    DATABASE = INSTANCE_DIR / "estoque.db"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
