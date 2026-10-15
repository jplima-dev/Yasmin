@echo off
setlocal
cd /d "%~dp0"
set "INK_PYTHON=%~dp0..\bridge\.venv\Scripts\python.exe"
if not exist "%INK_PYTHON%" set "INK_PYTHON=python"
"%INK_PYTHON%" "%~dp0launcher.py" --portable
endlocal
