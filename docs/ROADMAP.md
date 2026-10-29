# Plano de trabalho do portefólio

## Fase 1 — Organizar e documentar

- [x] Criar cópia limpa de trabalho.
- [x] Excluir bases de dados, backups, ambiente virtual e ficheiros locais do IDE.
- [x] Agrupar os recursos gráficos e ajustar os caminhos de carregamento.
- [x] Criar README, documentação inicial, dependências e `.gitignore`.
- [x] Criar testes de validação básicos.

## Fase 2 — Arranque e persistência

- [x] Implementar inicialização segura da base de dados quando não existir.
- [x] Eliminar a criação automática de utilizador/senha padrão.
- [x] Pedir criação do primeiro Administrador no primeiro arranque.
- [x] Persistir nome e slogan da empresa na base de dados.
- [x] Testar inicialização repetida e persistência em SQLite temporário.
- [ ] Testar migração de uma cópia de base antiga e confirmar que não se perdem dados.
- [ ] Testar visualmente o diálogo de primeiro Administrador e o login em Windows real.

## Fase 3 — Testes e fiabilidade

- [x] Criar testes automatizados para os principais componentes de segurança e persistência.
- [x] Validar integridade SQLite em base temporária.
- [x] Validar criação e verificação de backups.
- [ ] Aumentar gradualmente a cobertura de CRUD, permissões, exportações e restauro.
- [ ] Fazer teste manual de regressão no Windows com dados fictícios.

## Fase 4 — Refatoração gradual

- [ ] Reduzir o tamanho da aplicação principal extraindo um módulo de cada vez.
- [ ] Manter testes de regressão em cada alteração.
- [ ] Uniformizar nomes de funções e comentários, sem alterações visuais não solicitadas.

## Fase 5 — GitHub e apresentação profissional

- [x] Rever o `.gitignore`.
- [x] Publicar o projeto no GitHub.
- [x] Utilizar Pull Request para integrar alterações na `main`.
- [x] Criar README orientado para portefólio.
- [x] Criar documentação técnica para entrevistas.
- [x] Adicionar CI com GitHub Actions.
- [ ] Adicionar capturas de ecrã reais usando apenas dados fictícios.
- [ ] Decidir se o repositório será público ou continuará privado.

## Próximo passo recomendado

A partir daqui, novas funcionalidades não são obrigatórias para apresentar o projeto. O maior retorno para o portefólio vem de:

1. uma demonstração visual limpa;
2. capturas de ecrã com dados fictícios;
3. uma explicação curta da arquitetura;
4. capacidade de explicar decisões técnicas numa entrevista;
5. evolução gradual dos testes e da refatoração.
