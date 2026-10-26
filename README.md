# TB Software — Gestão de Clientes

Projeto pessoal desenvolvido em Python, com interface gráfica Tkinter e base de dados SQLite.

## Funcionalidades

- Cadastro, pesquisa, edição e remoção de clientes
- Registo de particulares e empresas
- Utilizadores, perfis e permissões
- Histórico e auditoria
- Lembretes e notificações
- Relatórios e exportação
- Backups e restauro local
- Recuperação de senha por código de uso único
- Interface Tkinter com recursos gráficos próprios

## Tecnologias

Python 3, Tkinter/ttk, SQLite, Pillow, openpyxl, ReportLab e unittest.

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
└── .gitignore
```

## Instalação

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

O Tkinter deve estar disponível na instalação do Python usada no Windows.

## Base de dados

A base de dados é local e não deve ser versionada. O programa cria as tabelas necessárias quando executado pela primeira vez e permite configurar o primeiro Administrador.

Nunca publique dados reais de clientes, palavras-passe, backups ou credenciais.

## Arranque no Windows

O projeto inclui scripts VBS/PowerShell para iniciar automaticamente apenas `interface_clientes.py` com `pythonw.exe`, sem janela de consola. O instalador permite escolher a localização do arquivo principal.

## Estado

Projeto pessoal em desenvolvimento e validação. O repositório será usado para versionamento, documentação e portfólio.
