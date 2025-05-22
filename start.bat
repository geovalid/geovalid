@echo off
setlocal

set "bin_dir=%cd%\bin"
if not exist "%bin_dir%" (
    echo "bin" not found. Run "setup.bat" first.
    exit /b
)

set "Scripts_dir=%bin_dir%\Scripts"
set "PATH=%Scripts_dir%;%bin_dir%;%PATH%"

python main.py

pause