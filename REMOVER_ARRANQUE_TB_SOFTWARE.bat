@echo off
setlocal
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
for %%F in ("%STARTUP%\TB_Software_Arranque.vbs" "%STARTUP%\TB_Software.vbs" "%STARTUP%\TB Software.vbs" "%STARTUP%\arranque_TB_Software.vbs" "%STARTUP%\interface_cliente_5.1.6.vbs") do if exist "%%~F" del /Q "%%~F" >nul 2>&1
echo Arranques antigos do TB Software removidos.
pause
