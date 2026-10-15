@echo off
setlocal
cd /d "%~dp0"
title Diagnostico - Organizador Local

echo === DIAGNOSTICO DO ORGANIZADOR ===
echo.

where py >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
) else (
    set "PY=python"
)

echo Python:
%PY% --version
if errorlevel 1 goto :no_python

echo.
echo WebSockets:
%PY% -c "import websockets; print('OK - websockets', websockets.__version__)"
if errorlevel 1 echo FALHOU - rode: %PY% -m pip install websockets

echo.
echo package.json:
if exist "%~dp0package.json" (echo OK - encontrado) else (echo FALHOU - package.json nao esta nesta pasta)

echo.
echo npm:
where npm.cmd
npm.cmd --version

echo.
echo Agora executando o agente com console visivel.
echo Se existir um erro, ele aparecera abaixo.
echo.
%PY% "%~dp0organizer_agent.pyw"
goto :end

:no_python
echo FALHOU - Python nao encontrado.

:end
echo.
pause
