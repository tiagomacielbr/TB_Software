# Notas da revisão técnica

## Estado atual

O TB Software encontra-se numa versão funcional de portefólio, com documentação, testes automatizados, CI, pipeline de release Windows e licença MIT.

## O que foi preservado

- O ficheiro de aplicação `interface_clientes.py`.
- Os módulos auxiliares `banco.py` e `clientes.py`.
- Os recursos gráficos ativos em `assets/`.
- As funcionalidades já implementadas na aplicação.

## Organização atual

- Código principal separado dos recursos gráficos.
- Documentação técnica concentrada em `docs/`.
- Testes automatizados em `tests/`.
- Dependências declaradas em `requirements.txt` e `requirements-dev.txt`.
- Dados locais, backups, ambientes virtuais e ficheiros privados excluídos pelo `.gitignore`.

## Verificações efetuadas

- Compilação sintática do código ativo e dos módulos auxiliares.
- Testes unitários da validação de NIF.
- Testes de inicialização segura.
- Testes de persistência em SQLite temporário.
- Verificação de integridade SQLite.
- Verificação de recursos gráficos.
- Verificação do pacote de trabalho para evitar publicação de dados locais e ficheiros privados.
- Pipeline de CI configurado no GitHub Actions.
- Pipeline de release Windows com testes antes da criação do executável.
- Release `v1.0.2` publicada com sucesso.

## Pontos de atenção

1. **Validação da interface:** os testes automatizados não substituem uma regressão manual completa no Windows.
2. **Operações de ponta a ponta:** CRUD, permissões, relatórios, exportações, lembretes, backups e restauração podem receber testes dedicados.
3. **Proteção de dados em repouso:** SQLite e backups continuam a ser ficheiros locais e não são encriptados em repouso.
4. **Arquitetura:** `interface_clientes.py` ainda concentra muitas responsabilidades e pode ser refatorado gradualmente.
5. **Screenshots:** devem utilizar apenas dados fictícios antes de serem publicados no README.

## Estratégia de evolução

A próxima etapa deve privilegiar alterações pequenas e testadas:

1. adicionar um teste;
2. extrair uma responsabilidade;
3. executar a suíte;
4. validar manualmente no Windows quando necessário;
5. integrar a alteração na branch `main`.

A prioridade é reduzir regressões enquanto o projeto evolui.
