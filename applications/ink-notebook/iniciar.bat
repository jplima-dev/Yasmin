@echo off
setlocal
cd /d "%~dp0"

rem Procura o .venv na pasta do projeto e, se nao achar, na pasta acima.
set "VENV=%~dp0.venv"
if not exist "%VENV%\Scripts\activate.bat" set "VENV=%~dp0..\.venv"
if not exist "%VENV%\Scripts\activate.bat" (
  echo .venv nao encontrado. Executando instalar.bat ...
  call instalar.bat
  set "VENV=%~dp0.venv"
)
if not exist "%VENV%\Scripts\activate.bat" (
  echo ERRO: .venv indisponivel.
  pause
  exit /b 1
)

call "%VENV%\Scripts\activate.bat"
python -c "import flask" 2>nul || pip install -r requirements.txt

python run.py
pause
