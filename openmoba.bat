@echo off
setlocal
cd /d "%~dp0"
python main.py %*
if errorlevel 1 (
    echo.
    echo Ocorreu um erro ao iniciar o OpenMoba.
    pause
)
