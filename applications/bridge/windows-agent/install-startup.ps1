param(
    [switch]$EnableScreenShare,
    [switch]$EnableRemoteControl
)

$ErrorActionPreference = 'Stop'
$AgentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path (Split-Path -Parent $AgentRoot) '.venv\Scripts\pythonw.exe'
$Agent = Join-Path $AgentRoot 'agent.py'
$Config = Join-Path $env:LOCALAPPDATA 'Bridge\agent.json'
if (-not (Test-Path -LiteralPath $Python)) { throw "Ambiente virtual não encontrado em $Python" }
if (-not (Test-Path -LiteralPath $Config)) { throw 'Pareie o agente em primeiro plano antes de instalar a inicialização automática.' }
$AgentArguments = '"' + $Agent + '"'
if ($EnableScreenShare) { $AgentArguments += ' --enable-screen-share' }
if ($EnableRemoteControl) { $AgentArguments += ' --enable-remote-control' }
$Action = New-ScheduledTaskAction -Execute $Python -Argument $AgentArguments -WorkingDirectory $AgentRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'Bridge Agent' -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Mantém o Bridge conectado em segundo plano' -Force
Write-Host 'Bridge Agent configurado para iniciar no logon.'
