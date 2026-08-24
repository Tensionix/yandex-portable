@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Portable Template - Collect Third-Party Licenses

set "NO_PAUSE="
set "CLEAN_SWITCH="
set "PASS_ARGS="
:ARG_LOOP
if "%~1"=="" goto ARGS_DONE
if /I "%~1"=="/NOPAUSE" (
    set "NO_PAUSE=1"
    shift
    goto ARG_LOOP
)
if /I "%~1"=="/CLEAN" (
    set "CLEAN_SWITCH=/CLEAN"
    shift
    goto ARG_LOOP
)
if /I "%~1"=="/ENGINE=PYTHON" (
    shift
    goto ARG_LOOP
)
if /I "%~1"=="/ENGINE=POWERSHELL" (
    echo [WARN] PowerShell engine mode was removed. Python engine will be used.
    shift
    goto ARG_LOOP
)
if /I "%~1"=="/ENGINE=AUTO" (
    shift
    goto ARG_LOOP
)
set "PASS_ARGS=%PASS_ARGS% %~1"
shift
goto ARG_LOOP
:ARGS_DONE

for %%I in ("%~f0") do set "SCRIPT_DIR=%%~dpI"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
if not exist "%SCRIPT_DIR%\Run-Collect-ThirdPartyLicenses-Python.cmd" (
    if exist "%CD%\system_core\license\Run-Collect-ThirdPartyLicenses-Python.cmd" (
        set "SCRIPT_DIR=%CD%\system_core\license"
    ) else if exist "%CD%\Run-Collect-ThirdPartyLicenses-Python.cmd" (
        set "SCRIPT_DIR=%CD%"
    )
)

echo [INFO] Requested engine: python
if defined NO_PAUSE (
    call "%SCRIPT_DIR%\Run-Collect-ThirdPartyLicenses-Python.cmd" %CLEAN_SWITCH% %PASS_ARGS% /NOPAUSE
) else (
    call "%SCRIPT_DIR%\Run-Collect-ThirdPartyLicenses-Python.cmd" %CLEAN_SWITCH% %PASS_ARGS%
)
set "RC=%errorlevel%"
exit /b %RC%
