@echo off
setlocal

if not exist "bin" mkdir "bin"
set "bin_dir=%cd%\bin"
set "Scripts_dir=%bin_dir%\Scripts"
set "PATH=%Scripts_dir%;%bin_dir%;%PATH%"

set "py_url=https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
set "pip_url=https://bootstrap.pypa.io/pip/pip.pyz"
set "py_zip=%bin_dir%\python-3.12.8-embed-amd64.zip"
set "py_exe=%bin_dir%\python.exe"
set "pip_file=%bin_dir%\pip.pyz"
set "pypth_file=%bin_dir%\python312._pth"

if not exist "%py_zip%" (
    echo Downloading Python...
    curl -o "%py_zip%" "%py_url%"
)

if not exist "%pip_file%" (
    echo Downloading pip...
    curl -o "%pip_file%" "%pip_url%"
)

if not exist "%py_exe%" (
    echo Extracting Python...
    tar -xf "%py_zip%" -C "%bin_dir%"
    
    (
        echo python312.zip
        echo .
        echo.
        echo import site
    ) > "%pypth_file%"

    echo Setting up Python environment...
    call "%bin_dir%\python.exe" "%pip_file%" install setuptools
    
    if exist requirements.txt (
        call "%bin_dir%\python.exe" "%pip_file%" install -r requirements.txt
    )
)
