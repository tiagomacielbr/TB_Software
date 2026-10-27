ARRANQUE AUTOMATICO DO TB SOFTWARE

Para configurar o arranque automático:

1. Execute INSTALAR_ARRANQUE_VBS.bat
2. O programa abrirá uma janela para você escolher o arquivo interface_clientes.py.
3. Selecione o arquivo da instalação que deseja iniciar com o Windows.
4. O instalador localizará o pythonw.exe e criará o arranque oculto na pasta Startup do Windows.

O arranque usa o caminho completo do arquivo escolhido. Portanto, o projeto pode ficar em qualquer pasta.

Não é necessário certificado e não é usado cmd para iniciar o programa.

Para trocar a instalação usada no arranque, execute novamente INSTALAR_ARRANQUE_VBS.bat e escolha o novo interface_clientes.py.
