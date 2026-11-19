# Login e gestão de usuários

A adaptação do módulo do Patrick usa o login e as sessões do Django. As contas
existentes continuam válidas. O menu **Usuários** aparece para administradores
(superusuários Django). Ele permite criar contas, escolher o tipo e ativar ou
desativar outros usuários. Um administrador não pode desativar a própria conta
pela tela de gestão.

Para criar o primeiro administrador, use `python manage.py createsuperuser`.
A autenticação usa os validadores, a proteção CSRF e o hash de senha do Django.
Funcionários têm acesso às operações conforme as regras de cada módulo.

Em `DB_ENGINE=mysql`, a criação pela tela grava a conta e o perfil de estoque na
mesma transação. Administradores recebem `administracao`; funcionários podem ter
perfil de vendas, estoque ou produção. Contas criadas fora dessa tela precisam
de um registro com o mesmo login em `usuario` para acessar o estoque. Quando
o Django usa SQLite ou PostgreSQL, a criação pela tela só grava a conta Django.
Contas da aplicação Flask não são importadas automaticamente.
