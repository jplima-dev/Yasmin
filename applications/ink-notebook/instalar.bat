@echo off
cd /d "%~dp0"
echo [Ink Notebook] Criando ambiente virtual em .venv ...
where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
if not exist ".venv\Scripts\activate.bat" (
  echo ERRO: nao foi possivel criar o .venv. Verifique se o Python 3.9+ esta instalado.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Pronto! Agora use iniciar.bat
pause
