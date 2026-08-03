@echo off
setlocal
cd /d "%~dp0"

REM --- check python ---
where pythonw >nul 2>&1
if errorlevel 1 (
    echo Python не найден. Установи Python 3.9+ с python.org и отметь "Add to PATH".
    pause
    exit /b 1
)

REM --- install PyQt6 if missing ---
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo Устанавливаю PyQt6...
    python -m pip install --upgrade pip
    python -m pip install PyQt6
)

REM --- run without a console window ---
start "" pythonw "%~dp0deskfinity.py"
