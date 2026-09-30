@echo off
REM ===================================================================
REM  Dragon Tool Suite - build a standalone Windows executable.
REM
REM  Produces:  dist\DragonTools.exe  (single file, no Python needed)
REM
REM  Usage:  double-click this file, or run  build_exe.bat  in a terminal.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo(
echo === Dragon Tool Suite - EXE builder ===
echo(

REM --- Make sure Python is available -------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on your PATH.
    echo Install Python 3.10+ from https://www.python.org/ and re-run.
    goto :error
)

REM --- Create/reuse an isolated virtual environment ----------------
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv || goto :error
)
call ".venv\Scripts\activate.bat" || goto :error

REM --- Install dependencies (runtime + PyInstaller) ---------------
echo Installing dependencies from requirements.txt ...
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error

REM --- Build the executable ---------------------------------------
echo(
echo Building DragonTools.exe (this can take a couple of minutes) ...

REM Bundle the templates (code generation) and assets (field image).
REM Auton DTDs/files are read from the user-selected season folder at runtime,
REM so nothing auton-specific needs to be bundled.
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name DragonTools ^
    --add-data "templates;templates" ^
    --add-data "assets;assets" ^
    main.py || goto :error

echo(
echo ===================================================================
echo  Build complete:  "%CD%\dist\DragonTools.exe"
echo ===================================================================
goto :end

:error
echo(
echo *** BUILD FAILED - see the messages above. ***
endlocal
exit /b 1

:end
endlocal
pause
