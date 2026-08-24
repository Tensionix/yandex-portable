@echo off
setlocal EnableExtensions

title Audion Yandex Portable - Update Requirements Lock

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "REQ_IN=%ROOT%\install\requirements_full.in"
set "REQ_LOCK=%ROOT%\install\requirements_lock.txt"
set "PYTHON_CMD="
set "PYTHON_ARGS="

if exist "%ROOT%\runtime\python.exe" (
  set "PYTHON_CMD=%ROOT%\runtime\python.exe"
  goto HAVE_PY
)

py -3.12 -V >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
  set "PYTHON_ARGS=-3.12"
  goto HAVE_PY
)

where python >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  goto HAVE_PY
)

echo [ERROR] Python was not found.
pause
exit /b 1

:HAVE_PY
echo [1/2] Ensuring pip-tools...
"%PYTHON_CMD%" %PYTHON_ARGS% -m pip install --disable-pip-version-check --upgrade pip-tools
if errorlevel 1 goto ERR_PIPTOOLS

echo [2/2] Compiling lock file...
"%PYTHON_CMD%" %PYTHON_ARGS% -m piptools compile "%REQ_IN%" -o "%REQ_LOCK%"
if errorlevel 1 goto ERR_COMPILE

echo [SUCCESS] Lock file updated:
echo %REQ_LOCK%
pause
exit /b 0

:ERR_PIPTOOLS
echo [ERROR] Failed to install or update pip-tools.
pause
exit /b 1

:ERR_COMPILE
echo [ERROR] Failed to compile requirements lock.
pause
exit /b 1
