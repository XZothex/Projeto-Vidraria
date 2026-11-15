# Módulo de cadastros — materiais e fornecedores

Responsável: XZothex · Branch: `feat/cadastros`

## O que existe
- `config/` — configurações do projeto (único projeto Django, lê `.env`).
- `cadastros/` — app do módulo: `models.py`, `forms.py`, `views.py`, `urls.py`, `validators.py`, `admin.py`, `mixins.py`, `migrations/`, `tests/`, `templates/`.
- `templates/base.html` — layout base reutilizável (Bootstrap 5, responsivo). Os outros módulos devem estender `base.html` e incluir seus links no menu.
- `templates/partials/` — formulário, paginação e selo de situação reutilizáveis.

## Instalar e executar
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
python manage.py migrate
python manage.py createsuperuser   # usuário padrão do Django, só para entrar
python manage.py popular_cadastros # dados fictícios (pode repetir sem duplicar)
python manage.py runserver
python manage.py test              # testes
```
Acesse http://127.0.0.1:8000/ e entre com o usuário criado.

## Banco de dados
- **Desenvolvimento local:** SQLite (`DB_ENGINE=sqlite`, padrão). O arquivo `db.sqlite3` é ignorado pelo Git.
- **Definitivo:** PostgreSQL. No `.env`: `DB_ENGINE=postgresql` + `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`; depois `python manage.py migrate`.
- Diferença conhecida: no SQLite a busca por texto não ignora maiúsculas/minúsculas em letras acentuadas (ex.: "ALUMÍNIO" x "alumínio"). No PostgreSQL funciona normalmente.

## Roteiro de demonstração (≈5 min)
1. Entrar → lista de **Materiais** (dados fictícios, paginação).
2. Buscar `temperado`, buscar `FER-`; filtrar categoria **Ferragem** e situação **Inativos**.
3. **Novo material**: salvar vazio (mostra erros); repetir um código existente (erro de duplicidade); espessura `0` (erro); cadastrar uma **ferragem** sem tipo de vidro/cor/espessura (permitido).
4. Abrir **Detalhes** → **Inativar** (confirmação, POST) → filtrar Inativos → **Reativar**.
5. **Fornecedores**: buscar por nome e por CNPJ (com ou sem pontuação); tentar CNPJ inválido e CNPJ repetido; mostrar que dois fornecedores sem CPF/CNPJ e com o mesmo nome são aceitos.
6. Mostrar o ponto de integração do login (`cadastros/mixins.py`) e a ausência de saldo/quantidade no cadastro (`cadastros/models.py`, docstring).

## Git: branch e Pull Request
```bash
git clone https://github.com/XZothex/Projeto-Vidraria.git
cd Projeto-Vidraria
git checkout -b feat/cadastros
# copie os arquivos deste pacote para a raiz do clone (não sobrescreva o README.md existente)
git status                          # confira: sem .env, sem db.sqlite3
git add .
git commit -m "feat(cadastros): cadastro e consulta de materiais e fornecedores"
git push -u origin feat/cadastros
```
Abra o Pull Request no GitHub (`feat/cadastros` → `main`) e peça revisão. **Não faça o merge** antes do alinhamento com a equipe.

## Pontos a alinhar com os colegas
1. **Banco/modelos:** o responsável pelo banco já tem `Material`/`Fornecedor`? Se sim, reaproveitar e ajustar as migrações (hoje: `cadastros/migrations/0001_initial.py`).
2. **Estrutura do projeto:** o repositório só tinha o README; este pacote cria `config/`, `manage.py`, `requirements.txt`, `.gitignore` e `.env.example`. Combinar quem é dono desses arquivos para evitar conflito.
3. **Login e permissões:** hoje só exige usuário autenticado (`cadastros/mixins.py`) e há login/logout provisórios em `config/urls.py` + `templates/registration/login.html`. Substituir pelo módulo de login; definir quem pode cadastrar/inativar.
4. **Chaves estrangeiras:** módulos de entradas, pedidos, cortes e sobras devem apontar para `Material` e `Fornecedor` com `on_delete=PROTECT` (nada é apagado, só inativado). Também decidir se materiais/fornecedores inativos aparecem nas telas deles.
5. **Vínculo material × fornecedor:** não existe no cadastro (o mesmo material pode vir de vários fornecedores); deve nascer nos recebimentos/pedidos.
6. **Unidade de controle × peças físicas:** chapas, peças e sobras (largura, altura, custo, quantidade) ficam fora do cadastro; combinar o modelo com quem cuida de cortes e sobras. A conversão de área (largura_mm × altura_mm ÷ 1.000.000) fica com esse módulo.
7. **Listas de opções:** confirmar categorias, tipos de vidro e unidades; formato do código (ex.: `VID-TEMP-8-INC`).
8. **Menu, página inicial e `base.html`:** hoje `/` redireciona para a lista de materiais; o dashboard é de outro módulo.
9. **Nomes de apps/tabelas:** o app se chama `cadastros` (tabelas `cadastros_material`, `cadastros_fornecedor`); confirmar antes de outros módulos dependerem disso.

## Correções de integridade
- CPF/CNPJ preenchido com letras ou caracteres inválidos é recusado, em vez de virar um documento vazio. Campo realmente vazio continua permitido.
- A carga de demonstração cria somente registros ausentes: repetir o comando preserva nomes, medidas e situação dos materiais existentes.
- A migração `0002` adiciona uma restrição no banco: espessura deve ser nula ou maior que zero. Execute `python manage.py migrate`. Caso uma base existente contenha espessuras inválidas, revise e corrija esses registros antes de aplicar a migração; nenhum dado é corrigido ou apagado automaticamente.
- As permissões de acesso continuam sendo um ponto de integração com o módulo responsável.
