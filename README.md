# Controle de Estoque de Vidros — autenticação

## Requisitos
Python 3.10 ou superior.

## Instalação no Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Criar o primeiro administrador
Execute uma única vez:
```powershell
python app.py criar-admin
```
Informe nome, usuário e senha (mínimo 8 caracteres).

## Executar
```powershell
python app.py
```
Acesse http://127.0.0.1:5000.

## Incluído
- Login e logout por sessão.
- Hash seguro de senha com Werkzeug.
- SQLite criado automaticamente em instance/estoque.db.
- Perfis administrador e funcionário.
- Proteção das rotas no servidor e resposta 403 para acesso não autorizado.
- Cadastro e ativação/desativação de usuários pelo administrador.
- Proteção CSRF nos formulários.

## Antes de publicar
Configure uma SECRET_KEY aleatória e secreta no ambiente, desative debug, use HTTPS e COOKIE_SECURE=1. Não use o servidor de desenvolvimento do Flask em produção.
