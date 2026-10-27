# TB Software — Gestão de Clientes

Projeto pessoal desenvolvido em Python, com interface gráfica Tkinter e base de dados SQLite. O objetivo principal deste repositório é demonstrar competências de programação, organização de código, persistência de dados, interface gráfica e testes.

> **Estado:** versão final em validação local antes da publicação no GitHub.

## Funcionalidades presentes no código

- Cadastro, pesquisa, edição e remoção de clientes.
- Registo de particulares e empresas, com suporte a passaporte e validação de campos.
- Utilizadores, perfis e permissões.
- Histórico de atendimento e auditoria.
- Lembretes com data/hora e notificações durante a execução.
- Relatórios, filtros e exportação para CSV, Excel e PDF.
- Cópias de segurança e restauro da base de dados.
- Tema claro/escuro e recursos visuais personalizados.
- Recuperação de senha por código de uso único, com cópia para a área de transferência.

Esta lista descreve funcionalidades presentes no código, não uma certificação de que todos os fluxos foram testados em Windows.

## Tecnologias

- Python 3
- Tkinter / ttk
- SQLite (`sqlite3`)
- Pillow (carregamento/redimensionamento de imagens)
- openpyxl (exportação Excel)
- ReportLab (geração de PDF; o código também inclui alternativas para alguns cenários)
- `unittest` para os testes incluídos

## Estrutura do repositório

```text
TB_Software/
├── interface_clientes.py  # Aplicação principal
├── banco.py                    # Conexão e inicialização segura SQLite
├── clientes.py                 # Funções auxiliares/legadas de clientes e NIF
├── assets/
│   ├── tb_software_logo.png
│   ├── dashboard/              # Ícones dos cartões do dashboard
│   └── icones_menu/             # Ícones do menu lateral
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROJECT_REVIEW.md
│   └── ROADMAP.md
├── tests/
├── requirements.txt
└── .gitignore
```

Os módulos permanecem na raiz nesta primeira fase para evitar alterações desnecessárias nas importações. As imagens foram agrupadas em `assets/`, e os recursos gráficos são carregados diretamente de assets/.

## Preparar o ambiente de desenvolvimento

Num terminal aberto nesta pasta, cria um ambiente virtual e instala as dependências:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

O módulo Tkinter deve estar disponível na instalação do Python usada no Windows.

## Base de dados e primeira execução

**Não coloques uma base de dados real no GitHub.** O ficheiro da base de dados é local e está ignorado pelo Git. A aplicação cria as tabelas base quando necessário, sem criar uma conta ou senha padrão. Numa base vazia, apresenta um formulário para criar o primeiro Administrador com uma senha própria (mínimo de 10 caracteres). A senha é armazenada no formato PBKDF2 usado pela aplicação. Em executáveis Windows, o banco fica em `%LOCALAPPDATA%\TB Software\banco.db`; em modo de código-fonte, fica junto de `banco.py`. Para testes, o caminho pode ser indicado pela variável de ambiente `TB_SOFTWARE_DB_PATH`.

As instalações antigas que ainda tenham o hash conhecido de `admin/1234` são obrigadas a substituir essa senha no início de sessão. A inicialização não substitui nem apaga tabelas já existentes.

Para desenvolver usando dados, cria uma base exclusivamente de teste, com dados fictícios. Nunca uses no repositório nomes, NIFs, contactos, palavras-passe ou históricos de pessoas reais.

## Segurança do repositório

- `.gitignore` exclui bases SQLite, backups, ambiente virtual, caches, logs e material de licenciamento privado.
- Não incluir chaves privadas, licenças de utilizadores, credenciais nem ficheiros de configuração pessoal.
- A ferramenta/variante de licenciamento offline não faz parte desta primeira organização; primeiro será necessário resolver as dependências e testar a integração.
- Ainda não foi definido um ficheiro de licença de código aberto. Decide a licença do repositório antes de o publicar publicamente.

## Limitações conhecidas

Consultar [`docs/PROJECT_REVIEW.md`](docs/PROJECT_REVIEW.md) e [`docs/ROADMAP.md`](docs/ROADMAP.md). O arranque automático do Windows usa VBS + `pythonw.exe` para iniciar apenas `interface_clientes.py`, sem janela de consola. A instalação final deve continuar a ser validada no Windows do utilizador.
