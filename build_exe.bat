@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo ============================================
echo   EchoHalls - build exe
echo ============================================

rem NOTE: never put a bare > or < inside an echo line here.
rem cmd treats it as redirection and will silently overwrite the file
rem named after it. That once turned a freshly built exe into an
rem 11-byte text file.

rem ---- [1/4] pick interpreter -------------------------------------------
rem PATH's python is often Anaconda on this machine, so it goes last.
set PY=
if defined EH_PY set PY=%EH_PY%
if not defined PY (py -3.12 -c "import sys" >nul 2>&1 && set PY=py -3.12)
if not defined PY (py -3.11 -c "import sys" >nul 2>&1 && set PY=py -3.11)
if not defined PY (py -3.9  -c "import sys" >nul 2>&1 && set PY=py -3.9)
if not defined PY (python -c "import sys" >nul 2>&1 && set PY=python)
if not defined PY goto nopython
echo [1/4] interpreter: %PY%
%PY% -c "import sys;print(sys.version)"

rem ---- [2/4] deps -------------------------------------------------------
rem NEVER trust pip's exit code here: broken package metadata in the
rem Anaconda env makes any pip command die while listing packages.
echo [2/4] checking deps
%PY% -c "import pygame, PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo     installing pygame / pyinstaller ...
    %PY% -m pip install --upgrade pygame pyinstaller
    %PY% -c "import pygame, PyInstaller" >nul 2>&1
    if errorlevel 1 goto nodeps
)
echo     ok

rem ---- [3/4] selftest ---------------------------------------------------
echo [3/4] selftest
%PY% main.py --selftest
if errorlevel 1 goto selftestfail

rem ---- [4/4] build ------------------------------------------------------
echo [4/4] building
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%PY% -m PyInstaller --noconfirm --clean EchoHalls.spec
if errorlevel 1 goto buildfail
if not exist "dist\EchoHalls.exe" goto buildfail

set SZ=0
for %%F in ("dist\EchoHalls.exe") do set SZ=%%~zF
echo     output size: !SZ! bytes
if !SZ! LSS 1000000 goto toosmall

echo.
echo ============================================
echo   DONE. Output file: dist\EchoHalls.exe
echo ============================================
echo If double-clicking the exe does nothing, build the debug version:
echo     %PY% -m PyInstaller --noconfirm --clean EchoHalls_debug.spec
echo and run dist\EchoHalls_debug\EchoHalls_debug.exe in a console.
echo A launch log is written to %%USERPROFILE%%\echohalls_launch.log
goto end

:nopython
echo [ERROR] No usable Python found. Set EH_PY, e.g.:  set EH_PY=py -3.12
goto end
:nodeps
echo [ERROR] pygame / pyinstaller are still not importable.
echo         Try:  %PY% -m pip install --user pygame pyinstaller
goto end
:selftestfail
echo [ERROR] selftest failed - not building.
goto end
:buildfail
echo [ERROR] PyInstaller failed. See the log above.
goto end
:toosmall
echo [ERROR] dist\EchoHalls.exe is only !SZ! bytes - the output was damaged
echo         after PyInstaller finished. Add the dist folder to your
echo         antivirus exclusions and rebuild.
goto end

:end
echo.
pause
