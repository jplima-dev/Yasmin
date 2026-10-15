$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimePython = 'C:\Users\gugas\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $RuntimePython)) {
    $RuntimePython = (Get-Command py -ErrorAction Stop).Source
    & $RuntimePython -3.12 -m venv (Join-Path $ProjectRoot '.venv')
} else {
    & $RuntimePython -m venv (Join-Path $ProjectRoot '.venv')
}
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $ProjectRoot 'requirements.txt')
Write-Host "Bridge preparado. Inicie com .\scripts\start.ps1"

