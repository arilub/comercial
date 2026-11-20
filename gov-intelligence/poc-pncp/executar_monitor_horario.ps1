$ErrorActionPreference = "Stop"
$base = "C:\ARILUB-CONSULTORIA-SEVERO\GOV-INTELLIGENCE"
$python = "C:\Users\AriLub\AppData\Local\Programs\Python\Python314\python.exe"
$script = Join-Path $base "scripts\monitor_horario_pncp_v1.py"
$logs = Join-Path $base "logs"
$logfile = Join-Path $logs ("gov_horario_" + (Get-Date -Format "yyyyMMdd") + ".log")
try {
    if (!(Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python nao encontrado: $python" }
    if (!(Test-Path -LiteralPath $script -PathType Leaf)) { throw "Script nao encontrado: $script" }
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $inicio = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logfile -Value ("=== INICIO " + $inicio + " ===") -Encoding UTF8
    & $python -u $script --base $base --python $python --max-paginas 8 --intervalo 4 --executar 2>&1 | Out-File -FilePath $logfile -Append -Encoding utf8
    $code = $LASTEXITCODE
    Add-Content -LiteralPath $logfile -Value ("=== FIM " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " CODIGO=" + $code + " ===") -Encoding UTF8
    exit $code
} catch {
    $msg = "FALHA LAUNCHER " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $_.Exception.Message
    try { Add-Content -LiteralPath $logfile -Value $msg -Encoding UTF8 } catch {}
    Write-Error $msg
    exit 1
}
