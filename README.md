# TB Software — Gestão de Clientes

![CI](https://github.com/tiagomacielbr/TB_Software/actions/workflows/ci.yml/badge.svg)

Aplicação desktop de gestão de clientes desenvolvida em **Python**, com **Tkinter/ttk** e **SQLite**.

O projeto foi construído como aplicação prática de portefólio, com foco em persistência de dados, autenticação, segurança de passwords, auditoria, backups, exportação de relatórios e testes automatizados.

## Visão geral

O TB Software simula um sistema de gestão utilizado por uma pequena empresa para manter clientes, utilizadores, atendimentos, lembretes e configurações locais.

### Principais funcionalidades

- 👥 Cadastro, pesquisa, edição e remoção de clientes
- 🧾 Suporte a particulares e empresas
- 🇵🇹 Validação de NIF
- 🔐 Autenticação de utilizadores, perfis e permissões
- 🔑 Passwords protegidas com PBKDF2 e salt aleatório
- ♻️ Recuperação de password por código temporário e de uso único
- 📝 Histórico de atendimento
- 🛡️ Sistema de auditoria
- ⏰ Lembretes e notificações
- 📊 Relatórios, filtros e exportação
- 📄 Exportação para CSV, Excel e PDF
- 💾 Backup e restauração da base SQLite
- 🎨 Interface gráfica com tema e recursos visuais personalizados
- 🗄️ Migrações de estrutura da base sem apagar dados existentes
- 🧪 Testes automatizados com pytest

## Tecnologias

| Tecnologia | Utilização |
|---|---|
| Python 3 | Linguagem principal |
| Tkinter / ttk | Interface gráfica desktop |
| SQLite | Persistência local |
| hashlib / secrets | Segurança e geração de credenciais |
| Pillow | Recursos gráficos |
| openpyxl | Exportação Excel |
| ReportLab | Geração de PDF |
| pytest | Testes automatizados |
| Git / GitHub | Versionamento e colaboração |

## Arquitetura atual

A aplicação é atualmente monolítica, com a maior parte da interface e lógica de negócio concentrada em `interface_clientes.py`.

A camada SQLite foi centralizada em `banco.py`, responsável por:

- determinar o caminho da base;
- abrir conexões;
- configurar `busy_timeout`, foreign keys e sincronização;
- criar as tabelas base;
- persistir configurações da empresa.

Os recursos gráficos ficam em `assets/` e a documentação técnica em `docs/`.

Mais detalhes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Estrutura

```text
TB_Software/
├── interface_clientes.py
├── banco.py
├── clientes.py
├── assets/
├── docs/
├── tests/
├── requirements.txt
├── requirements-dev.txt
├── .github/
│   └── workflows/
│       └── ci.yml
└── .gitignore
```

## Instalação no Windows

Abra o PowerShell na pasta do projeto:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Depois execute:

```powershell
python interface_clientes.py
```

> O projeto foi desenvolvido para Windows. O Tkinter precisa estar disponível na instalação do Python.

## Testes

Para executar a suíte:

```powershell
python -m pytest tests -q
```

Última validação local utilizada nesta versão:

```text
9 passed, 3 subtests passed
```

O GitHub Actions também executa os testes automaticamente em Windows a cada push ou Pull Request.

## Dados e segurança

A base de dados é local e **não faz parte do repositório**.

- `*.db`, `*.sqlite3` e backups estão no `.gitignore`.
- Não devem ser adicionados NIFs, contactos, passwords ou históricos reais.
- A instalação vazia não cria uma password padrão.
- A aplicação permite configurar o primeiro Administrador.
- Em modo executável, a base é armazenada no perfil local do utilizador.

Para testes automatizados, o caminho da base pode ser controlado por `TB_SOFTWARE_DB_PATH`.

## Limitações conhecidas

Este é um projeto de portefólio em evolução. A interface principal ainda concentra bastante código em um único módulo e pode ser refatorada gradualmente.

Também existem fluxos que merecem testes manuais adicionais no Windows, especialmente:

- primeira execução;
- login e permissões;
- exportações;
- backups e restauração;
- utilização com uma base antiga.

Essas limitações estão documentadas em [docs/PROJECT_REVIEW.md](docs/PROJECT_REVIEW.md).

## Documentação do projeto

- [Arquitetura](docs/ARCHITECTURE.md)
- [Revisão técnica](docs/PROJECT_REVIEW.md)
- [Roadmap](docs/ROADMAP.md)
- [Apresentação técnica para entrevistas](docs/PORTFOLIO.md)

## Objetivo de portefólio

Este projeto demonstra competências práticas em:

- desenvolvimento de aplicações desktop;
- Python e programação estruturada;
- SQL e SQLite;
- autenticação e segurança básica;
- manipulação de ficheiros;
- tratamento de erros;
- testes automatizados;
- Git e GitHub;
- documentação técnica;
- manutenção e evolução incremental de software.

## Autor

**Tiago Rogerio Santos Maciel**

Projeto desenvolvido para demonstrar evolução prática em programação e preparação para oportunidades profissionais na área de tecnologia.
