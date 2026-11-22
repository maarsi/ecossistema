@echo off
rem Roda saude_windows.ps1 sem depender da politica de execucao e guarda TUDO que aparecer na tela,
rem inclusive erro, em saude_windows_console.txt (para o Claude ler se o relatorio nao sair).
set SAUDE_SEM_PAUSA=1
echo Rodando a checagem do Windows (leva de 1 a 2 minutos)...
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\95 - TEMP\saude_windows.ps1" > "D:\95 - TEMP\saude_windows_console.txt" 2>&1
echo.
echo Terminado, codigo %ERRORLEVEL%. Pode fechar esta janela e avisar o Claude.
pause
