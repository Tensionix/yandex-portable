@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Audion Yandex Portable - GUI

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "APP_FILE=%BASE_DIR%\system_core\ui_nicegui\window.py"

if /I "%AUDION_GUI_RESOLVE_ONLY%"=="1" goto SKIP_ELEVATE
if /I "%AUDION_GUI_NO_ELEVATE%"=="1" goto SKIP_ELEVATE
if /I "%AUDION_GUI_ELEVATE%"=="1" (
  call :ENSURE_ADMIN
  if errorlevel 1 exit /b %ERRORLEVEL%
  if /I "%GUI_ELEVATION_STARTED%"=="1" exit /b 0
)

:SKIP_ELEVATE
call :RESOLVE_PYTHON
if errorlevel 1 goto NO_PYTHON

if /I "%AUDION_GUI_RESOLVE_ONLY%"=="1" exit /b 0

if not exist "%APP_FILE%" goto NO_APP

if /I "%PYTHON_IS_WINDOWED%"=="1" (
  start "" "%PYTHON_CMD%" %PYTHON_ARGS% "%APP_FILE%"
  exit /b 0
)

"%PYTHON_CMD%" %PYTHON_ARGS% "%APP_FILE%"
exit /b %ERRORLEVEL%

:ENSURE_ADMIN
fltmc >nul 2>nul
if not errorlevel 1 exit /b 0

echo [INFO] This template can run the GUI elevated when the target project needs Administrator rights.
echo [INFO] Requesting UAC elevation...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$script = '%~f0'; $work = '%BASE_DIR%'; Start-Process -FilePath $env:ComSpec -ArgumentList @('/d','/c','call', ('\"' + $script + '\"')) -WorkingDirectory $work -Verb RunAs"
if errorlevel 1 (
  echo [ERROR] UAC elevation request failed or was cancelled.
  pause
  exit /b 1
)
set "GUI_ELEVATION_STARTED=1"
exit /b 0

:RESOLVE_PYTHON
set "PYTHON_CMD="
set "PYTHON_ARGS="
set "PYTHON_IS_WINDOWED="

if defined AUDION_GUI_PYTHON if exist "%AUDION_GUI_PYTHON%" (
  set "PYTHON_CMD=%AUDION_GUI_PYTHON%"
  exit /b 0
)

if /I not "%AUDION_GUI_CONSOLE%"=="1" if exist "%BASE_DIR%\runtime\pythonw.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\pythonw.exe"
  set "PYTHON_IS_WINDOWED=1"
  exit /b 0
)

if exist "%BASE_DIR%\runtime\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python.exe"
  exit /b 0
)

if /I not "%AUDION_GUI_CONSOLE%"=="1" if exist "%BASE_DIR%\runtime\python\pythonw.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python\pythonw.exe"
  set "PYTHON_IS_WINDOWED=1"
  exit /b 0
)

if exist "%BASE_DIR%\runtime\python\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python\python.exe"
  exit /b 0
)

py -3.12 -V >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
  set "PYTHON_ARGS=-3.12"
  exit /b 0
)

exit /b 1

:NO_APP
echo [ERROR] GUI wrapper was not found:
echo %APP_FILE%
pause
exit /b 1

:NO_PYTHON
echo [ERROR] Python runtime was not resolved.
echo Supported locations:
echo   runtime\pythonw.exe
echo   runtime\python.exe
echo   runtime\python\pythonw.exe
echo   runtime\python\python.exe
echo   py -3.12
echo   AUDION_GUI_PYTHON=C:\path\to\python.exe
echo.
echo Build the portable runtime first or run this launcher from a real project folder.
echo Set AUDION_GUI_CONSOLE=1 to run GUI in console debug mode.
echo Set AUDION_GUI_ELEVATE=1 to request UAC at startup.
echo Set AUDION_GUI_NO_ELEVATE=1 to skip startup UAC elevation.
pause
exit /b 1
