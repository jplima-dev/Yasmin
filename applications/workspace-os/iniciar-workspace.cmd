@echo off
setlocal
cd /d "%~dp0"

where pyw >nul 2>&1
if not errorlevel 1 (
    start "" pyw -3 "%~dp0launcher.py"
    exit /b 0
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw "%~dp0launcher.py"
    exit /b 0
)

if exist "%~dp0..\bridge\.venv\Scripts\pythonw.exe" (
    start "" "%~dp0..\bridge\.venv\Scripts\pythonw.exe" "%~dp0launcher.py"
    exit /b 0
)

echo.
echo [ERRO] Python 3 nao foi encontrado.
echo Instale o Python 3.11 ou superior e marque a opcao de adicionar o Python ao PATH.
echo.
pause
exit /b 1
