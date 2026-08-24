@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Audion Yandex Portable - Verify Portable Env

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

if not exist "%ROOT%\runtime\python.exe" goto ERR_PYTHON
if not exist "%ROOT%\system_core\doctor.py" goto ERR_DOCTOR

call "%ROOT%\install\Check-CmdEncoding.cmd"
if errorlevel 1 goto ERR_CMD_ENCODING

"%ROOT%\runtime\python.exe" "%ROOT%\system_core\doctor.py" --project-root "%ROOT%"
set "RC=%errorlevel%"
if not "%RC%"=="0" goto DONE_VERIFY

set "GUI_APP=%ROOT%\system_core\ui_nicegui\app.py"
if exist "%GUI_APP%" (
    echo.
    echo [GUI] Running NiceGUI smoke check...
    "%ROOT%\runtime\python.exe" "%GUI_APP%" --smoke
    set "RC=%errorlevel%"
)

:DONE_VERIFY
pause
exit /b %RC%

:ERR_PYTHON
echo [ERROR] runtime\python.exe was not found.
pause
exit /b 1

:ERR_DOCTOR
echo [ERROR] doctor.py was not found.
pause
exit /b 1

:ERR_CMD_ENCODING
echo [ERROR] CMD encoding check failed.
pause
exit /b 1
