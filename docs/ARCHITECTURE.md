# Arquitetura atual

## Visão geral

A aplicação é atualmente monolítica: `interface_clientes.py` contém a inicialização do Tkinter, a maior parte das janelas e a lógica de negócio. O objetivo desta primeira passagem não é reescrever essa estrutura, mas torná-la compreensível e segura de trabalhar antes de fazer refatorações graduais.

## Módulos

- **`interface_clientes.py`**: autenticação, janelas, cadastro/pesquisa/alteração/exclusão, configurações, relatórios, exportação, lembretes, auditoria e backups.
- **`banco.py`**: centraliza o caminho e a conexão SQLite, inicializa as tabelas base sem conta ou senha padrão e guarda as configurações persistentes da empresa.
- **`clientes.py`**: funções auxiliares para validar NIF e consultar dados de cliente; ainda conserva funcionalidades antigas de consola.
- **`assets/`**: logótipo e imagens utilizadas pela interface.

## Fluxo de dados

1. A interface chama `conectar_banco()`.
2. As funções da interface executam consultas parametrizadas com SQLite.
3. Alterações são confirmadas com `commit()` e, em diversos fluxos, desfeitas com `rollback()` perante um erro.
4. A aplicação tem rotinas de migração de schema. A aplicação chama `inicializar_banco()` antes das migrações. O caminho é independente da pasta de execução; no código-fonte usa a pasta do projeto e, num executável Windows, usa `%LOCALAPPDATA%\TB Software\banco.db`. É possível substituir o caminho em testes definindo `TB_SOFTWARE_DB_PATH`.

## Decisões nesta fase

- Preservar os nomes de módulos principais e a interface para reduzir o risco de regressões.
- Centralizar os recursos gráficos em `assets/` e manter fallback temporário para os caminhos antigos.
- Não versionar dados de clientes nem cópias de segurança.
- Não integrar o código de licenciamento offline nesta cópia até reparar e testar a variante separadamente.

## Inicialização e configurações

- Uma instalação sem utilizadores abre o formulário de configuração do primeiro Administrador.
- A senha inicial tem mínimo de 10 caracteres e é guardada pelo mecanismo PBKDF2 da aplicação.
- Nome e slogan são persistidos em `configuracoes_app` e recuperados na inicialização.
- A ferramenta nunca cria uma conta `admin` com uma senha conhecida.

## Próximas oportunidades de refatoração

Depois de garantir uma primeira execução segura e testes de regressão, separar gradualmente acesso a dados, validação, exportação e janelas em módulos próprios. Cada extração deve ter testes e ser feita numa alteração pequena.
