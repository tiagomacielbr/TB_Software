# TB Software — Sistema de Gestão de Clientes

[![CI](https://github.com/tiagomacielbr/TB_Software/actions/workflows/ci.yml/badge.svg)](https://github.com/tiagomacielbr/TB_Software/actions)

Aplicação desktop de **gestão de clientes**, desenvolvida em **Python**, com interface gráfica em **Tkinter/ttk** e persistência local em **SQLite**.

O projeto foi desenvolvido como aplicação prática de portefólio, com foco em **gestão de dados, autenticação, segurança de passwords, auditoria, backups, exportação de relatórios, testes automatizados e CI/CD**.

## 📌 Sobre o projeto

O TB Software simula uma solução utilizada por uma pequena empresa para centralizar:

- dados de clientes;
- utilizadores e permissões;
- histórico de atendimentos;
- lembretes;
- relatórios e exportações;
- backups;
- configurações da empresa.

O objetivo é demonstrar a capacidade de desenvolver e manter uma aplicação desktop completa, desde a interface e persistência dos dados até testes, versionamento e distribuição.

## 🚀 Principais funcionalidades

### Gestão de clientes

- Cadastro de clientes
- Pesquisa, edição e remoção
- Suporte para particulares e empresas
- Validação de NIF

### Autenticação e segurança

- Login de utilizadores
- Perfis e permissões
- Configuração do primeiro Administrador na primeira execução
- Passwords protegidas com **PBKDF2 + salt aleatório**
- Recuperação de password por código temporário e de utilização única
- Compatibilidade com hashes anteriores durante a migração

### Gestão e acompanhamento

- Histórico de atendimentos
- Sistema de auditoria
- Lembretes e notificações
- Configurações persistentes da empresa

### Relatórios e exportação

- Relatórios com filtros
- Exportação para CSV
- Exportação para Excel
- Exportação para PDF

### Base de dados

- SQLite
- Inicialização automática da estrutura
- Migrações de schema
- Integridade referencial
- Backups e restauração
- Base de dados local por utilizador

## 🛠️ Tecnologias

| Tecnologia | Utilização |
|---|---|
| **Python 3** | Linguagem principal |
| **Tkinter / ttk** | Interface gráfica desktop |
| **SQLite** | Persistência local |
| **hashlib / secrets** | Segurança e geração de credenciais |
| **Pillow** | Recursos gráficos |
| **openpyxl** | Exportação para Excel |
| **ReportLab** | Geração de PDF |
| **pytest** | Testes automatizados |
| **Git / GitHub** | Versionamento |
| **GitHub Actions** | CI/CD |
| **PyInstaller** | Geração do executável Windows |

## 🏗️ Arquitetura atual

A aplicação encontra-se atualmente numa arquitetura **monolítica**, com a maior parte da interface e lógica de negócio concentrada em:

`interface_clientes.py`

O acesso à base de dados está centralizado em:

`banco.py`

O módulo `clientes.py` contém funções auxiliares relacionadas com validação e consulta de clientes.

Os recursos gráficos encontram-se em:

`assets/`

e a documentação técnica em:

`docs/`

Mais detalhes:

- [Arquitetura](docs/ARCHITECTURE.md)
- [Revisão técnica](docs/PROJECT_REVIEW.md)
- [Roadmap](docs/ROADMAP.md)
- [Guia de apresentação técnica](docs/PORTFOLIO.md)

## 📂 Estrutura do projeto

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
│       ├── ci.yml
│       └── release.yml
└── .gitignore
```

## 💻 Instalação no Windows

Abra o PowerShell na pasta do projeto:

```powershell
git clone https://github.com/tiagomacielbr/TB_Software.git
cd TB_Software

py -m venv .venv
.venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Execute a aplicação:

```powershell
python interface_clientes.py
```

> O projeto foi desenvolvido para Windows. O Tkinter precisa estar disponível na instalação do Python.

## 🧪 Testes automatizados

Execute a suíte de testes com:

```powershell
python -m pytest tests -q
```

Última validação local desta versão:

```text
9 passed, 3 subtests passed
```

Os testes utilizam bases SQLite temporárias para evitar alterar os dados reais do utilizador.

A suíte cobre, entre outros pontos:

- inicialização da base de dados;
- criação das tabelas;
- integridade SQLite;
- hash de passwords;
- compatibilidade com hash legado;
- códigos de recuperação;
- migrações de schema;
- criação e validação de backups.

## 🔄 Integração contínua

O projeto utiliza **GitHub Actions** para executar os testes automaticamente.

O workflow de CI:

1. prepara um ambiente Windows;
2. instala Python 3.13;
3. instala as dependências;
4. executa `pytest`.

O CI é executado em pushes para as branches configuradas e em Pull Requests para `main`.

## 📦 Release Windows

O projeto possui um workflow específico para criação do executável Windows.

Quando uma tag no formato:

`v*`

é publicada, o GitHub Actions:

1. instala as dependências;
2. executa os testes;
3. instala PyInstaller;
4. gera `TB_Software.exe`;
5. publica o executável na GitHub Release.

A versão de apresentação atual é:

**TB Software v1.0.2**

## 🔐 Dados e segurança

A base de dados é armazenada localmente e **não faz parte do repositório**.

O `.gitignore` evita o versionamento de ficheiros como:

```text
*.db
*.sqlite3
backups
.venv
__pycache__
```

A instalação vazia não cria uma conta `admin` com password conhecida. O primeiro Administrador é configurado pelo utilizador.

Durante demonstrações e entrevistas devem ser utilizados exclusivamente **dados fictícios**.

Para testes automatizados, o caminho da base pode ser controlado pela variável:

`TB_SOFTWARE_DB_PATH`

## ⚠️ Limitações conhecidas

O TB Software é uma versão funcional de portefólio em evolução.

A interface principal ainda concentra bastante código em `interface_clientes.py`, sendo possível realizar uma refatoração gradual para separar responsabilidades.

Também existem fluxos que merecem testes manuais adicionais no Windows:

- primeira execução;
- login e permissões;
- exportações;
- backups e restauração;
- migração de uma base de dados antiga.

Além disso:

- SQLite e os backups não estão encriptados em repouso;
- a licença do repositório ainda não foi definida;
- a cobertura de testes de ponta a ponta ainda pode ser ampliada.

Esses pontos estão documentados em [Revisão técnica](docs/PROJECT_REVIEW.md) e no [Roadmap](docs/ROADMAP.md).

## 🗺️ Roadmap

Próximas melhorias previstas:

- aumentar a cobertura de testes;
- testar fluxos completos de CRUD;
- testar permissões e exportações;
- testar restauração de backups;
- realizar testes de regressão no Windows;
- refatorar gradualmente `interface_clientes.py`;
- separar acesso a dados, validação, exportação e interface;
- adicionar capturas de ecrã reais utilizando apenas dados fictícios;
- decidir a licença do projeto.

A estratégia é evoluir através de alterações pequenas e testadas, reduzindo o risco de regressões.

## 🎯 Objetivo de portefólio

O TB Software foi desenvolvido para demonstrar competências práticas em:

- **Python**
- **SQL / SQLite**
- **Tkinter**
- **Autenticação e segurança**
- **Manipulação de ficheiros**
- **Tratamento de erros**
- **Testes automatizados**
- **Git / GitHub**
- **GitHub Actions / CI/CD**
- **Documentação técnica**
- **Manutenção e evolução incremental de software**

O objetivo não é demonstrar apenas conhecimento de sintaxe Python, mas capacidade de trabalhar com um software real em evolução.

## 🎥 Demonstração

Fluxo recomendado para apresentar o projeto:

1. Abrir a aplicação.
2. Demonstrar a autenticação.
3. Mostrar o dashboard.
4. Criar um cliente fictício.
5. Pesquisar e editar o cliente.
6. Mostrar histórico e auditoria.
7. Demonstrar um lembrete.
8. Mostrar uma exportação.
9. Demonstrar backup/restauração.
10. Apresentar os testes automatizados.
11. Mostrar o GitHub Actions.

> **Importante:** utilizar apenas dados fictícios durante demonstrações e entrevistas.

## 👨‍💻 Autor

**Tiago Rogerio Santos Maciel**

Projeto desenvolvido como portefólio para demonstrar evolução prática em programação e preparação para oportunidades profissionais na área de tecnologia.
