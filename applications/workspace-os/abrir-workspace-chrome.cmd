@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\reiniciar-workspace-chrome.ps1"
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel reiniciar o Workspace.
    echo Consulte a mensagem acima para corrigir o problema.
    echo.
    pause
    exit /b 1
)

exit /b 0
