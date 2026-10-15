param(
    [string]$PublicUrl
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $PSScriptRoot 'start.ps1'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Execute .\scripts\setup.ps1 antes de instalar a inicialização automática.'
}

$PowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $StartScript + '"'
if ($PublicUrl) {
    $Arguments += ' -PublicUrl "' + $PublicUrl.TrimEnd('/') + '"'
}

$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName 'Bridge Core' `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description 'Mantém o Bridge Core disponível em segundo plano após o logon' `
    -Force | Out-Null

Write-Host 'Bridge Core configurado para iniciar automaticamente no logon.'

