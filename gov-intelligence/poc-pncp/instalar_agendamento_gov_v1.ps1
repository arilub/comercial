param([switch]$Ativar)
$ErrorActionPreference = "Stop"
$nome = "GOV_INTELLIGENCE_ATUALIZACAO_HORARIA"
$base = "C:\ARILUB-CONSULTORIA-SEVERO\GOV-INTELLIGENCE"
$launcher = Join-Path $base "scripts\executar_monitor_horario.ps1"
$py = Join-Path $base "scripts\monitor_horario_pncp_v1.py"
if (!(Test-Path -LiteralPath $launcher -PathType Leaf)) {throw "Launcher ausente"}
if (!(Test-Path -LiteralPath $py -PathType Leaf)) {throw "Monitor Python ausente"}
$triggers = @(6..21 | ForEach-Object {
    New-ScheduledTaskTrigger -Daily -At ("{0:D2}:40" -f $_)
})
$ps = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
$action = New-ScheduledTaskAction -Execute $ps -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $launcher + '"')
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable:$false
$existing = Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    throw "Tarefa GOV ja existe; nenhuma substituicao automatica. Auditoria manual necessaria."
}
if (-not $Ativar) {
    Write-Host "MODO SIMULACAO: nenhuma tarefa instalada."
    $triggers | ForEach-Object { Write-Host $_.StartBoundary }
    exit 0
}
Register-ScheduledTask -TaskName $nome -Action $action -Trigger $triggers -Settings $settings -Description "GOV Intelligence PNCP CE: diario a cada hora das 06h40 as 21h40. Sem PIF ou Comercial." | Out-Null
$t=Get-ScheduledTask -TaskName $nome
if ($t.Triggers.Count -ne 16) {
    Disable-ScheduledTask -TaskName $nome | Out-Null
    throw "Quantidade incorreta de disparos; tarefa desativada"
}
Write-Host "TAREFA GOV CRIADA: " $t.TaskName
Write-Host "ESTADO:" $t.State
Write-Host "TOTAL GATILHOS:" $t.Triggers.Count
$t.Triggers | ForEach-Object {Write-Host "HORARIO:" $_.StartBoundary}
Get-ScheduledTaskInfo -TaskName $nome | Select-Object NextRunTime,LastRunTime,LastTaskResult | Format-List
Write-Host "PIF E COMERCIAL: NAO ALTERADOS"
Write-Host "AVISO: HTML de apresentacao ainda nao e regenerado por esta tarefa."
