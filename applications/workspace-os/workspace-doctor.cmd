@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0launcher.py" --doctor %*
    exit /b %errorlevel%
)

where python >nul 2>&1
if not errorlevel 1 (
    python "%~dp0launcher.py" --doctor %*
    exit /b %errorlevel%
)

if exist "%~dp0..\bridge\.venv\Scripts\python.exe" (
    "%~dp0..\bridge\.venv\Scripts\python.exe" "%~dp0launcher.py" --doctor %*
    exit /b %errorlevel%
)

if exist "%~dp0..\driver\.venv\Scripts\python.exe" (
    "%~dp0..\driver\.venv\Scripts\python.exe" "%~dp0launcher.py" --doctor %*
    exit /b %errorlevel%
)

echo.
echo [ERRO] Python 3.11 ou superior nao foi encontrado.
echo Instale o Python ou recrie o ambiente virtual do Bridge/InkDriver.
echo.
exit /b 1
