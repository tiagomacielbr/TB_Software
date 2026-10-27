# Plano de trabalho do portefólio

## Fase 1 — Organizar e documentar

- [x] Criar cópia limpa de trabalho.
- [x] Excluir bases de dados, backups, ambiente virtual e ficheiros locais do IDE.
- [x] Agrupar os recursos gráficos e ajustar os caminhos de carregamento.
- [x] Criar README, documentação inicial, dependências e `.gitignore`.
- [x] Criar testes de validação básicos.

## Fase 2 — Arranque e persistência

- [x] Implementar inicialização segura da base de dados quando não existir.
- [x] Eliminar a criação automática de utilizador/senha padrão e forçar a troca da credencial antiga conhecida `admin/1234`.
- [x] Pedir criação do primeiro Administrador com credenciais definidas no primeiro arranque.
- [x] Persistir nome e slogan da empresa na base de dados.
- [x] Testar inicialização repetida e persistência em SQLite temporário, sem apagar os registos existentes.
- [ ] Testar migração de uma cópia de base antiga e confirmar que não se perdem dados.
- [ ] Testar visualmente o diálogo de primeiro Administrador e o login em Windows real.

## Fase 3 — Testes e fiabilidade

- [ ] Separar funções de dados/validação suficientes para permitir testes sem abrir a interface.
- [ ] Testar operações CRUD, permissões, exportação, backups e restauro em base temporária.
- [ ] Fazer teste manual de regressão no Windows com dados fictícios.
- [ ] Corrigir os erros encontrados e atualizar a documentação.

## Fase 4 — Refatoração gradual

- [ ] Reduzir o tamanho da aplicação principal extraindo um módulo de cada vez.
- [ ] Manter testes de regressão em cada alteração.
- [ ] Uniformizar nomes de funções e comentários, sem alterações visuais não solicitadas.

## Fase 5 — GitHub e candidaturas

- [ ] Rever segurança e garantir que o histórico Git também não contém dados ou segredos.
- [ ] Definir licença do código antes de publicar.
- [ ] Preparar capturas de ecrã usando dados fictícios.
- [ ] Publicar README e instruções claras de configuração.
- [ ] Acrescentar o projeto ao CV e preparar uma explicação técnica para entrevistas.
