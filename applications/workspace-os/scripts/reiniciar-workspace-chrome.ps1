param(
    [switch]$SkipChrome
)

$ErrorActionPreference = "Stop"

$WorkspaceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$EcosystemRoot = (Resolve-Path -LiteralPath (Join-Path $WorkspaceRoot "..")).Path
$LauncherPath = Join-Path $WorkspaceRoot "launcher.py"
$WorkspaceUrl = "http://127.0.0.1:8790"
$HealthUrl = "$WorkspaceUrl/api/health"
$ChromeProfileDirectory = "Default" # Gustavo - gugasksk@gmail.com

function Test-WorkspaceOnline {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
        return $response.status -eq "ok"
    }
    catch {
        return $false
    }
}

function Get-WorkspaceProcessId {
    try {
        $diagnostics = Invoke-RestMethod -Uri "$WorkspaceUrl/api/diagnostics" -TimeoutSec 2
        if ($diagnostics.processId) {
            return [int]$diagnostics.processId
        }
    }
    catch {
        $listener = Get-NetTCPConnection -State Listen -LocalPort 8790 -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($listener) {
            return [int]$listener.OwningProcess
        }
    }
    return $null
}

function Wait-WorkspaceState([bool]$Online, [int]$Attempts = 60) {
    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        if ((Test-WorkspaceOnline) -eq $Online) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Close-WorkspaceChromeWindow {
    if (-not ("WorkspaceWindow.NativeMethods" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;

namespace WorkspaceWindow {
    public static class NativeMethods {
        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll")]
        public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

        [DllImport("user32.dll")]
        public static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern bool PostMessage(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);
    }
}
"@
    }

    $windows = [System.Collections.Generic.List[System.IntPtr]]::new()
    $callback = [WorkspaceWindow.NativeMethods+EnumWindowsProc] {
        param([IntPtr]$windowHandle, [IntPtr]$state)

        if (-not [WorkspaceWindow.NativeMethods]::IsWindowVisible($windowHandle)) {
            return $true
        }

        $title = [System.Text.StringBuilder]::new(512)
        [void][WorkspaceWindow.NativeMethods]::GetWindowText($windowHandle, $title, $title.Capacity)
        if ($title.ToString() -ne "Workspace OS") {
            return $true
        }

        [uint32]$ownerProcessId = 0
        [void][WorkspaceWindow.NativeMethods]::GetWindowThreadProcessId($windowHandle, [ref]$ownerProcessId)
        $process = Get-Process -Id $ownerProcessId -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq "chrome") {
            $windows.Add($windowHandle)
        }
        return $true
    }

    [void][WorkspaceWindow.NativeMethods]::EnumWindows($callback, [IntPtr]::Zero)
    foreach ($windowHandle in $windows) {
        # WM_CLOSE fecha somente a janela de aplicativo do Workspace.
        [void][WorkspaceWindow.NativeMethods]::PostMessage($windowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
    }
}

function Stop-Workspace {
    $processId = Get-WorkspaceProcessId
    try {
        $session = Invoke-RestMethod -Uri "$WorkspaceUrl/api/session" -Method Get -TimeoutSec 3
        $headers = @{ "X-Workspace-Token" = $session.token; "Idempotency-Key" = [guid]::NewGuid().ToString() }
        Invoke-RestMethod -Uri "$WorkspaceUrl/api/shutdown" -Method Post -Headers $headers -ContentType "application/json" -Body "{}" -TimeoutSec 3 | Out-Null
    }
    catch {
        # Versoes anteriores nao possuem encerramento gracioso; o PID confirmado pela API/porta e o fallback.
    }
    if (Wait-WorkspaceState -Online $false -Attempts 20) {
        return
    }
    if ($processId) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    if (-not (Wait-WorkspaceState -Online $false -Attempts 20)) {
        throw "A porta 8790 continua ocupada e nao pode ser reiniciada."
    }
}

function Find-PythonLauncher {
    $pyw = Get-Command "pyw.exe" -ErrorAction SilentlyContinue
    if ($pyw) {
        return @{ FilePath = $pyw.Source; Arguments = @("-3", $LauncherPath, "--no-browser", "--with-driver") }
    }
    $pythonw = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
    if ($pythonw) {
        return @{ FilePath = $pythonw.Source; Arguments = @($LauncherPath, "--no-browser", "--with-driver") }
    }
    $bridgePython = Join-Path $EcosystemRoot "bridge\.venv\Scripts\pythonw.exe"
    if (Test-Path -LiteralPath $bridgePython) {
        return @{ FilePath = $bridgePython; Arguments = @($LauncherPath, "--no-browser", "--with-driver") }
    }
    throw "Python 3.11 ou superior nao foi encontrado."
}

function Find-Chrome {
    $command = Get-Command "chrome.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $candidates = @(
        (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    throw "Google Chrome nao foi encontrado."
}

$wasOnline = Test-WorkspaceOnline
if ($wasOnline) {
    Write-Host "Reiniciando o Workspace que ja estava ativo..."
    Stop-Workspace
    Close-WorkspaceChromeWindow
}
else {
    Write-Host "A porta 8790 esta livre. Iniciando o Workspace..."
}

$python = Find-PythonLauncher
Start-Process -FilePath $python.FilePath -ArgumentList $python.Arguments -WorkingDirectory $WorkspaceRoot -WindowStyle Hidden

if (-not (Wait-WorkspaceState -Online $true -Attempts 80)) {
    throw "O Workspace nao respondeu na porta 8790 apos 20 segundos."
}

if (-not $SkipChrome) {
    $chrome = Find-Chrome
    Start-Process -FilePath $chrome -ArgumentList @(
        "--profile-directory=$ChromeProfileDirectory",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        $WorkspaceUrl
    )
}

Write-Host $(if ($SkipChrome) { "Workspace reiniciado em modo de validacao." } else { "Workspace reiniciado e aberto no Google Chrome." })
