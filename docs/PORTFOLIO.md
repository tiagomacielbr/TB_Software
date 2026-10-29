# TB Software — Guia de apresentação técnica

## 1. O que é?

O TB Software é uma aplicação desktop de gestão de clientes criada em Python. A aplicação usa Tkinter para a interface e SQLite para persistência local.

O objetivo do projeto é demonstrar capacidade de desenvolver uma aplicação real do início ao fim, e não apenas scripts isolados.

## 2. Problema que o projeto resolve

Uma pequena empresa precisa de centralizar:

- dados de clientes;
- utilizadores e permissões;
- histórico de atendimento;
- lembretes;
- relatórios;
- backups;
- configurações da empresa.

O TB Software reúne essas tarefas numa aplicação desktop local.

## 3. Decisões técnicas importantes

### SQLite centralizado

O acesso à base foi concentrado em `banco.py`. Isso evita espalhar a configuração da conexão pelo projeto e facilita testes.

A conexão aplica:

- `busy_timeout`;
- `foreign_keys = ON`;
- `synchronous = NORMAL`.

### Segurança de passwords

A aplicação usa PBKDF2 com salt aleatório para novas passwords.

A recuperação de password utiliza códigos temporários armazenados como hash e invalidados depois do uso.

### Compatibilidade

Existe suporte para reconhecer hashes antigos e permitir migração para o formato atual sem deixar o projeto dependente de uma password padrão.

### Backups

Os backups são tratados como ficheiros locais e validados antes de serem utilizados pela aplicação.

### Testes

Os testes usam SQLite temporário para evitar alterar a base real do utilizador.

A suíte atual valida, entre outros pontos:

- inicialização da base;
- criação das tabelas;
- integridade SQLite;
- hash de passwords;
- compatibilidade com hash legado;
- expiração de códigos de recuperação;
- migrações de schema;
- criação e validação de backup.

## 4. Como explicar o projeto numa entrevista

Uma apresentação de aproximadamente 60 segundos pode ser:

> "Este é o TB Software, uma aplicação desktop que desenvolvi em Python para gestão de clientes. Usei Tkinter para a interface e SQLite para a persistência. Além do CRUD de clientes, implementei autenticação, perfis, recuperação de password, auditoria, histórico, lembretes, relatórios, exportações e backup. Uma parte importante do projeto foi tratar segurança e manutenção: as passwords novas usam PBKDF2 com salt, a base tem uma camada centralizada de conexão e criei testes automatizados usando bases temporárias. O projeto está versionado no GitHub e possui CI para executar os testes automaticamente."

## 5. Perguntas técnicas que você deve conseguir responder

### Por que SQLite?

Porque o sistema é desktop e local. SQLite evita a necessidade de instalar e administrar um servidor de banco de dados.

### Por que usar PBKDF2?

Porque password não deve ser armazenada em texto simples. O PBKDF2 torna a tentativa de descobrir a password por força bruta mais custosa.

### Por que usar uma base temporária nos testes?

Para os testes serem repetíveis e não destruírem os dados reais do utilizador.

### Por que separar `banco.py`?

Para centralizar conexão, caminho e configuração do SQLite e reduzir duplicação.

### Por que ainda existe um módulo monolítico?

Porque a prioridade desta fase foi estabilizar e documentar a aplicação existente. A refatoração pode ser feita gradualmente, extraindo responsabilidades sem alterar todo o sistema de uma vez.

### O projeto está terminado?

A resposta profissional é:

> "A versão apresentada está funcional e testada nos principais componentes, mas continuo com um roadmap de evolução. Os próximos passos são aumentar a cobertura de testes, fazer mais testes manuais no Windows e refatorar gradualmente o módulo principal."

Essa resposta demonstra consciência técnica sem afirmar que software real está perfeito.

## 6. O que não apresentar

Não utilizar na demonstração:

- dados reais de clientes;
- NIFs reais;
- passwords reais;
- backups reais;
- ficheiros privados;
- chaves de licenciamento.

Use sempre dados fictícios.

## 7. Como demonstrar em 3 minutos

1. Abrir o programa.
2. Mostrar a tela de login.
3. Entrar com um utilizador de demonstração.
4. Criar um cliente fictício.
5. Pesquisar e editar o cliente.
6. Mostrar histórico/auditoria.
7. Mostrar um lembrete.
8. Mostrar uma exportação.
9. Mostrar a área de backup.
10. Explicar rapidamente os testes e o GitHub Actions.

## 8. Mensagem principal para recrutadores

O ponto forte do projeto não é a quantidade de telas.

É demonstrar que você consegue pensar em:

**interface + dados + segurança + testes + manutenção + versionamento.**
