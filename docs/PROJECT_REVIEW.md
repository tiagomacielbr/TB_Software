# Notas da revisão inicial

## O que foi preservado

- O ficheiro de aplicação `interface_clientes.py` escolhido como base.
- Os módulos auxiliares `banco.py` e `clientes.py`.
- Os recursos gráficos ativos: logótipo, imagens do dashboard e ícones do menu lateral.
- As funcionalidades que já estão implementadas no código original.

## Alterações desta primeira fase

- Criada uma cópia de trabalho organizada, sem ambiente virtual, base de dados local, cópias de segurança, cache de Python ou configuração privada do IDE.
- Os recursos gráficos foram colocados em `assets/` e foram atualizados apenas os caminhos de carregamento na cópia de trabalho. Os recursos gráficos usam a estrutura organizada em assets/.
- Removido do caminho de pesquisa de imagens o caminho absoluto de desenvolvimento `/mnt/data/TB_Software_5_2_assets`.
- Acrescentados README, documentação inicial, dependências declaradas, `.gitignore` e testes básicos.

## Problemas conhecidos que ainda precisam de atenção

1. **Validação da interface:** os testes automatizados não substituem um teste manual em Windows com base de dados de teste.
2. **Operações de ponta a ponta:** criar/editar/excluir clientes, permissões, relatórios, exportações, lembretes, backups e restauro ainda precisam de testes de regressão dedicados.
3. **Licenciamento offline:** a variante de licenciamento não foi integrada nesta cópia de portefólio; a licença offline é uma preocupação separada e não deve acrescentar chaves privadas ao repositório.
4. **Proteção de dados em repouso:** SQLite e backups não estão encriptados. O `.gitignore` evita parte das publicações acidentais, mas não protege ficheiros roubados do computador.
5. **Licença do repositório:** ainda é necessário decidir se o código será publicado com uma licença de código aberto ou com todos os direitos reservados.

## Verificações efetuadas

- Compilação sintática do código ativo e dos módulos auxiliares.
- Testes unitários da validação de NIF com entradas sintéticas.
- Testes de inicialização segura: criação de tabelas sem utilizadores padrão, inicialização repetida preservando registos e persistência do nome/slogan.
- Verificação da existência dos recursos gráficos referenciados.
- Verificação do ZIP final para confirmar que não contém ficheiros de base de dados, backups, `.venv`, `.idea`, `__pycache__` nem chaves privadas.

A interface gráfica não foi iniciada nesta revisão. A inicialização de banco vazia foi testada com SQLite temporário, mas o diálogo Tkinter de primeira execução e a aplicação completa ainda precisam de validação no Windows.
