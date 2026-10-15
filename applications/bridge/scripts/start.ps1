param(
    [string]$PublicUrl
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Execute .\scripts\setup.ps1 primeiro.' }
try {
    $Running = Invoke-RestMethod -Uri 'http://127.0.0.1:8876/api/health' -TimeoutSec 2
    if ($Running.status -eq 'ok') {
        Write-Host "Bridge Core já está ativo (versão $($Running.version))."
        exit 0
    }
} catch {
    # Nenhum Core respondeu; esta instância pode iniciar normalmente.
}
$LocalAddress = $null
$RouteProbe = [System.Net.Sockets.UdpClient]::new()
try {
    $RouteProbe.Connect('1.1.1.1', 53)
    $LocalAddress = $RouteProbe.Client.LocalEndPoint.Address.ToString()
} catch {
    $LocalAddress = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.InterfaceAlias -notlike '*Loopback*' } |
        Select-Object -First 1 -ExpandProperty IPAddress
} finally {
    $RouteProbe.Dispose()
}
if ($PublicUrl) {
    $env:BRIDGE_PUBLIC_URL = $PublicUrl.TrimEnd('/')
} elseif ($LocalAddress) {
    # Recalcula em toda inicialização para não reutilizar o IP antigo do PowerShell.
    $env:BRIDGE_PUBLIC_URL = "http://${LocalAddress}:8876"
} else {
    $env:BRIDGE_PUBLIC_URL = 'http://127.0.0.1:8876'
}
Set-Location -LiteralPath $ProjectRoot
Write-Host "Painel local: http://127.0.0.1:8876"
Write-Host "Outros aparelhos: $env:BRIDGE_PUBLIC_URL"
& $Python run.py
