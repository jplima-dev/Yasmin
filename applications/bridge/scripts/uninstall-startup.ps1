$ErrorActionPreference = 'Stop'
$Task = Get-ScheduledTask -TaskName 'Bridge Core' -ErrorAction SilentlyContinue
if ($Task) {
    Unregister-ScheduledTask -TaskName 'Bridge Core' -Confirm:$false
    Write-Host 'Inicialização automática do Bridge Core removida.'
} else {
    Write-Host 'A tarefa Bridge Core não estava instalada.'
}

