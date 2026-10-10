@echo off
REM Startet das Plot-Cut-Panel.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Plot-Cut] Lege virtuelle Umgebung an...
    py -3.12 -m venv .venv
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call ".venv\Scripts\activate.bat"
)

python -m plot_cut.main %*
endlocal
