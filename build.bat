@echo off
REM Builds dist\MarkItDownGUI.exe  (run on Windows with Python 3.10+ installed and on PATH)
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error

pyinstaller --noconfirm --clean MarkItDownGUI.spec || goto :error

echo.
echo Build complete: %~dp0dist\MarkItDownGUI.exe
exit /b 0

:error
echo.
echo BUILD FAILED (error %errorlevel%)
exit /b 1
