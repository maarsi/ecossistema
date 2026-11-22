@echo off
rem Inicia o Syncthing do Windows (instalado pelo winget, que NAO cria inicio automatico). 22/11/2026.
set ST=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Syncthing.Syncthing_Microsoft.Winget.Source_8wekyb3d8bbwe\syncthing-windows-amd64-v2.1.5\syncthing.exe
if not exist "%ST%" (echo Nao achei o Syncthing em %ST% & pause & exit /b 1)
tasklist /FI "IMAGENAME eq syncthing.exe" | find /I "syncthing.exe" >nul && (echo O Syncthing ja esta rodando. & pause & exit /b 0)
echo Iniciando o Syncthing em segundo plano...
powershell -NoProfile -Command "Start-Process -FilePath $env:ST -ArgumentList '--no-browser' -WindowStyle Hidden"
timeout /t 10 /nobreak >nul
tasklist /FI "IMAGENAME eq syncthing.exe" | find /I "syncthing.exe" >nul && (echo OK: Syncthing rodando. Pode fechar e avisar o Claude.) || (echo FALHOU: o Syncthing nao ficou de pe. Avise o Claude.)
pause
