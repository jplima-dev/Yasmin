@echo off
setlocal
cd /d "%~dp0"
title Organizador Local

REM 1) Encontra um Python instalado.
where py >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
    goto :python_ok
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
    goto :python_ok
)

echo.
echo [ERRO] Python nao foi encontrado no PATH.
echo Instale o Python ou habilite o Python Launcher ^(py.exe^).
echo.
pause
exit /b 1

:python_ok
REM 2) Confere a dependencia. Se faltar, instala automaticamente.
%PY% -c "import websockets" >nul 2>&1
if errorlevel 1 (
    echo Preparando o agente pela primeira vez...
    %PY% -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo [ERRO] Nao consegui instalar a dependencia websockets.
        echo Execute manualmente: %PY% -m pip install websockets
        echo.
        pause
        exit /b 1
    )
)

REM 3) Inicia o agente sem deixar terminal aberto.
where pyw >nul 2>&1
if not errorlevel 1 (
    start "" pyw -3 "%~dp0organizer_agent.pyw" --background
) else (
    where pythonw >nul 2>&1
    if not errorlevel 1 (
        start "" pythonw "%~dp0organizer_agent.pyw" --background
    ) else (
        REM Fallback para instalacoes que possuem apenas py.exe/python.exe.
        powershell -NoProfile -WindowStyle Hidden -Command ^
          "Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c','%PY% \"%~dp0organizer_agent.pyw\" --background'"
    )
)

REM 4) Espera o agente assumir a porta 5173 (ou detectar o servidor ja aberto).
powershell -NoProfile -Command ^
  "$ok=$false; for($i=0;$i -lt 50;$i++){ try{$c=New-Object Net.Sockets.TcpClient; $a=$c.BeginConnect('127.0.0.1',5173,$null,$null); if($a.AsyncWaitHandle.WaitOne(150)){ $c.EndConnect($a); $c.Close(); $ok=$true; break }; $c.Close()}catch{}; Start-Sleep -Milliseconds 100 }; if($ok){exit 0}else{exit 1}"

if errorlevel 1 (
    echo.
    echo [ERRO] O agente nao conseguiu abrir a porta 5173.
    echo Vou executar o agente em modo de diagnostico para mostrar o erro.
    echo.
    %PY% "%~dp0organizer_agent.pyw"
    echo.
    echo Consulte tambem: "%~dp0organizer-agent.log"
    pause
    exit /b 1
)

REM 5) Abre o navegador. O agente foi iniciado com --background justamente
REM para evitar que ele e o CMD tentem abrir duas guias ao mesmo tempo.
start "" "http://127.0.0.1:5173/#/dashboard"
exit /b 0
