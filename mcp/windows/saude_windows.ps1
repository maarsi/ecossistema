# saude_windows.ps1 - checagem da maquina Windows (duebendorf). Item 8 da fila de 21/11/2026.
# REVISADO A MAO, sintaxe NAO conferida por ferramenta (sem PowerShell no ambiente de quem escreveu).
# So LE. Nao altera nada, nao imprime credencial: do config do Claude Desktop lista apenas NOMES
# de servidor. Relatorio em D:\95 - TEMP\saude_windows_<data>.md
# Rodar: botao direito > Executar com o PowerShell  (ou: powershell -ExecutionPolicy Bypass -File saude_windows.ps1)
$ErrorActionPreference = "SilentlyContinue"
$data = Get-Date -Format "yyyyMMdd_HHmm"
$saida = "D:\95 - TEMP\saude_windows_$data.md"
$L = New-Object System.Collections.Generic.List[string]
function Add($t) { $L.Add($t) }
function Est($ok, $item, $det) { $s = if ($ok -eq $true) { "OK  " } elseif ($ok -eq $false) { "FALHA" } else { "ATENCAO" }; Add "| $s | $item | $det |" }
Add "# Saude do Windows ($env:COMPUTERNAME) - $(Get-Date -Format 'dd/MM/yyyy HH:mm')"
Add ""; Add "| estado | item | detalhe |"; Add "|---|---|---|"

# 1. disco
foreach ($d in "C", "D") {
  $v = Get-PSDrive $d
  if ($v) { $livre = [math]::Round($v.Free / 1GB, 1); $tot = [math]::Round(($v.Used + $v.Free) / 1GB, 0)
    Est ($livre -gt 30) "disco ${d}:" "$livre GB livres de $tot GB" }
}
# 2. VPN de terceiro (incidente de 29/10: VPN do Norton capturou a rota e a ponte caiu com WinError 10013)
$vpn = Get-NetAdapter | Where-Object { $_.Status -eq "Up" -and ($_.InterfaceDescription -match "Norton|NortonLifeLock|Gen Digital|Avast SecureLine|WireGuard|OpenVPN|TAP-Windows") }
Est (-not $vpn) "VPN de terceiro ativa" ($(if ($vpn) { ($vpn.InterfaceDescription -join "; ") + " -> SUSPEITO N.1 se a ponte cair" } else { "nenhuma" }))
# 3. Tailscale e alcance da Ubuntu
$ts = Get-Service Tailscale
Est ($ts.Status -eq "Running") "servico Tailscale" "$($ts.Status)"
$p22 = Test-NetConnection 100.66.93.31 -Port 22 -WarningAction SilentlyContinue
$p11 = Test-NetConnection 100.66.93.31 -Port 11434 -WarningAction SilentlyContinue
Est ($p22.TcpTestSucceeded) "Ubuntu porta 22 (SSH da ponte)" "$($p22.TcpTestSucceeded)"
Est ($p11.TcpTestSucceeded) "Ubuntu porta 11434 (Ollama)" "$($p11.TcpTestSucceeded)"
# 4. Syncthing
$st = Get-Process syncthing
Est ([bool]$st) "processo Syncthing" ($(if ($st) { "rodando, pid $($st[0].Id)" } else { "PARADO" }))
$ign = "C:\Users\mateu\ecossistema\.stignore"
Est (Test-Path $ign) ".stignore da replica ecossistema" ($(if (Test-Path $ign) { "presente" } else { "AUSENTE: credencial que cair ali seria indexada" }))
$envsinc = Test-Path "C:\Users\mateu\ecossistema\.env"
Est (-not $envsinc) ".env dentro da pasta sincronizada" ($(if ($envsinc) { "EXISTE: remover (regra de 24/10)" } else { "ausente, correto" }))
# 5. Claude Desktop: config VIVO (o de %LOCALAPPDATA%\Claude-Data\claude_*), so nomes de servidor
$cfg = Get-ChildItem "$env:LOCALAPPDATA\Claude-Data" -Recurse -Filter claude_desktop_config.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($cfg) {
  $j = Get-Content $cfg.FullName -Raw | ConvertFrom-Json
  $nomes = @($j.mcpServers.PSObject.Properties.Name)
  Est ($nomes.Count -ge 9) "servidores MCP no config vivo" "$($nomes.Count): $($nomes -join ', ')"
  $bak = Get-ChildItem $cfg.DirectoryName -Filter "*antes_da_rotacao*"
  Est (-not $bak) "copia de seguranca de config com chave antiga" ($(if ($bak) { "$($bak.Count) arquivo(s) em $($cfg.DirectoryName): copia de config e exposicao igual a do original" } else { "nenhuma" }))
} else { Est $false "config vivo do Claude Desktop" "nao encontrado" }
# 6. ambientes Python dos servidores e a trava mcp<2
foreach ($v in "C:\TransportMCP\.venv", "D:\TransportMCP\.venv") {
  $py = "$v\Scripts\python.exe"
  if (Test-Path $py) {
    $ver = & $py -c "import importlib.metadata as m; print(m.version('mcp'))" 2>$null
    Est ($ver -and $ver -notmatch "^2\.") "mcp em $v" "versao $ver"
    $ini = Test-Path "$v\pip.ini"
    Est $ini "trava pip.ini (mcp<2) em $v" ($(if ($ini) { "presente" } else { "AUSENTE: pip install -U mcp derrubaria os servidores" }))
    # Pede EXPLICITAMENTE o mcp 2: com a trava, o pip tem de recusar. (Versao de 22/11 pedia "mcp" puro; como o
    # mcp ja estava instalado, o pip nao tinha nada a instalar e a checagem ficava sem prova.)
    $out = [string](& $py -m pip install "mcp>=2" --dry-run 2>&1)
    $okdry = if ($out -match "ResolutionImpossible|Cannot install|conflict|No matching distribution") { $true } elseif ($out -match "Would install.*mcp-2") { $false } else { $null }
    $res = if ($okdry -eq $true) { "pip RECUSOU mcp>=2: trava ativa" } elseif ($okdry -eq $false) { "pip INSTALARIA mcp 2: trava NAO funciona" } else { "resposta inesperada do pip" }
    Est $okdry "prova da trava em $v (--dry-run de mcp>=2)" $res
  } else { Est $false "ambiente $v" "nao existe" }
}
$tsr = & "D:\TransportMCP\.venv\Scripts\python.exe" -c "import truststore; print(truststore.__version__)" 2>$null
Est ([bool]$tsr) "truststore no venv do TomTom/Google" "$tsr"
# 7. reinicio pendente do Windows Update
$pend = Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
Est (-not $pend) "reinicio pendente (Windows Update)" "$pend"
Add ""; Add "Nada foi alterado. Gerado por saude_windows.ps1."
$L | Out-File -FilePath $saida -Encoding utf8
Write-Host "Relatorio: $saida"; Write-Host ($L -join "`n")
if (-not $env:SAUDE_SEM_PAUSA) { Read-Host "Enter para fechar" }
