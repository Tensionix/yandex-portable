@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

for %%A in ("%SCRIPT_DIR%") do set "HERE=%%~nxA"

set "ROOT=%SCRIPT_DIR%"
if /I "%HERE%"=="install" for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

call :MK "%ROOT%\input"
call :MK "%ROOT%\output"
call :MK "%ROOT%\logs"
call :MK "%ROOT%\report"
call :MK "%ROOT%\report\gui_smoke_screenshots"
call :MK "%ROOT%\workspace"
call :MK "%ROOT%\config"
call :MK "%ROOT%\config\icc"
call :MK "%ROOT%\data"
call :MK "%ROOT%\runtime"
call :MK "%ROOT%\wheelhouse"
call :MK "%ROOT%\release"
call :MK "%ROOT%\._runtime"
call :MK "%ROOT%\docs"
call :MK "%ROOT%\system_core"
call :MK "%ROOT%\system_core\core"
call :MK "%ROOT%\system_core\services"
call :MK "%ROOT%\system_core\ui_nicegui"
call :MK "%ROOT%\system_core\powershell"
call :MK "%ROOT%\system_core\license"
call :MK "%ROOT%\system_core\license\files"
call :MK "%ROOT%\system_core\license\fallbacks"
call :MK "%ROOT%\install"
call :MK "%ROOT%\install\download"
call :MK "%ROOT%\licenses"

exit /b 0

:MK
if not exist "%~1\" mkdir "%~1" >nul 2>nul
goto :eof
