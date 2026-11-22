# Cria o atalho de inicio automatico do Syncthing (22/11/2026). Tudo o que acontece vai para syncthing_inicio_log.txt.
$ErrorActionPreference = "Stop"
try {
  $st = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Syncthing.Syncthing_Microsoft.Winget.Source_8wekyb3d8bbwe\syncthing-windows-amd64-v2.1.5\syncthing.exe"
  "executavel: $st  existe: $(Test-Path $st)"
  $pasta = [Environment]::GetFolderPath("Startup")
  "pasta Inicializar: $pasta  existe: $(Test-Path $pasta)"
  if (-not (Test-Path $pasta)) { New-Item -ItemType Directory -Path $pasta | Out-Null; "pasta criada" }
  $lnk = Join-Path $pasta "Syncthing.lnk"
  $w = New-Object -ComObject WScript.Shell
  $s = $w.CreateShortcut($lnk)
  $s.TargetPath = $st; $s.Arguments = "--no-browser"; $s.WindowStyle = 7
  $s.WorkingDirectory = Split-Path $st
  $s.Save()
  "atalho: $lnk  existe: $(Test-Path $lnk)"
  if (Test-Path $lnk) { "RESULTADO: OK" } else { "RESULTADO: FALHOU (Save nao gravou)" }
} catch { "ERRO: $($_.Exception.GetType().Name): $($_.Exception.Message)"; "RESULTADO: FALHOU" }
