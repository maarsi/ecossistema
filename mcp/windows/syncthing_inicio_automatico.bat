@echo off
rem Cria o inicio automatico do Syncthing. Detalhes e erros em syncthing_inicio_log.txt. 22/11/2026.
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\95 - TEMP\syncthing_inicio_automatico.ps1" > "D:\95 - TEMP\syncthing_inicio_log.txt" 2>&1
type "D:\95 - TEMP\syncthing_inicio_log.txt"
pause
