@echo off
REM Startet VectorCraft mit aktiviertem Steuerkanal auf Port 7979.
REM Passe VC_EXE an den Installationspfad deiner VectorCraft-Version an.

set "VC_EXE=C:\Program Files\VectorCraft\vectorcraft.exe"
set "VC_PORT=7979"

if not exist "%VC_EXE%" (
    echo [Plot-Cut] VectorCraft nicht gefunden unter:
    echo    %VC_EXE%
    echo Bitte VC_EXE in start-vectorcraft.bat anpassen.
    pause
    exit /b 1
)

start "" "%VC_EXE%" --control %VC_PORT% %*
