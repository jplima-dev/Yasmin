@echo off
setlocal
if not exist "%~dp0Agent\launcher.py" (
    echo [ERRO] Arquivo Agent\launcher.py nao encontrado ao lado do inicializador.
    exit /b 1
)
cd /d "%~dp0Agent" || exit /b 1
set "PYTHONIOENCODING=utf-8"
if defined YASM_PYTHON goto executar
if exist "%~dp0.venv\Scripts\python.exe" set "YASM_PYTHON=%~dp0.venv\Scripts\python.exe"
if defined YASM_PYTHON goto executar
if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" set "YASM_PYTHON=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if defined YASM_PYTHON goto executar
if exist "%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe" set "YASM_PYTHON=%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe"
if defined YASM_PYTHON goto executar
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3 -u launcher.py > launcher.log 2>&1
    exit /b
)
set "YASM_PYTHON=python"
:executar
"%YASM_PYTHON%" -u launcher.py > launcher.log 2>&1
exit /b %errorlevel%
