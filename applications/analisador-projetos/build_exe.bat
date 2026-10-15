@echo off
setlocal
cd /d "%~dp0"

echo [1/5] Preparing virtual environment...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

echo [2/5] Updating pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/5] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [4/5] Running tests...
python -m unittest discover -s tests -v
if errorlevel 1 goto :error

echo [5/5] Building ProjectAnalyzer.exe...
python -m PyInstaller --noconfirm --clean ProjectAnalyzer.spec
if errorlevel 1 goto :error

echo.
echo Build completed successfully.
echo Executable: %CD%\dist\ProjectAnalyzer.exe
exit /b 0

:error
echo.
echo Build failed. Review the error above.
exit /b 1
