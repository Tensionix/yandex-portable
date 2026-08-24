@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Portable Template - Collect Third-Party Licenses (Python)

set "NO_PAUSE="
set "CLEAN_ARG="
set "PASS_ARGS="
:ARG_LOOP
if "%~1"=="" goto ARGS_DONE
if /I "%~1"=="/NOPAUSE" (
    set "NO_PAUSE=1"
    shift
    goto ARG_LOOP
)
if /I "%~1"=="/CLEAN" (
    set "CLEAN_ARG=--clean-output"
    shift
    goto ARG_LOOP
)
set "PASS_ARGS=%PASS_ARGS% %~1"
shift
goto ARG_LOOP
:ARGS_DONE

for %%I in ("%~f0") do set "SCRIPT_DIR=%%~dpI"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
if not exist "%SCRIPT_DIR%\collect_third_party_licenses.py" (
    if exist "%CD%\system_core\license\collect_third_party_licenses.py" (
        set "SCRIPT_DIR=%CD%\system_core\license"
    ) else if exist "%CD%\collect_third_party_licenses.py" (
        set "SCRIPT_DIR=%CD%"
    )
)
set "PY_COLLECTOR=%SCRIPT_DIR%\collect_third_party_licenses.py"
for %%I in ("%SCRIPT_DIR%\..\..") do set "ROOT=%%~fI"
if not exist "%ROOT%\system_core\license\collect_third_party_licenses.py" (
    if exist "%CD%\system_core\license\collect_third_party_licenses.py" set "ROOT=%CD%"
)

set "PY_EXE="
set "PY_ARGS="
if exist "%ROOT%\runtime\python.exe" (
    set "PY_EXE=%ROOT%\runtime\python.exe"
    goto PY_READY
)
if exist "%ROOT%\runtime\python\python.exe" (
    set "PY_EXE=%ROOT%\runtime\python\python.exe"
    goto PY_READY
)
py -3.12 -V >nul 2>nul
if not errorlevel 1 (
    set "PY_EXE=py"
    set "PY_ARGS=-3.12"
    goto PY_READY
)
py -3 -V >nul 2>nul
if not errorlevel 1 (
    set "PY_EXE=py"
    set "PY_ARGS=-3"
    goto PY_READY
)
where python.exe >nul 2>nul
if not errorlevel 1 (
    set "PY_EXE=python"
    goto PY_READY
)
where python3.exe >nul 2>nul
if not errorlevel 1 (
    set "PY_EXE=python3"
    goto PY_READY
)
:PY_READY

echo [INFO] Requested engine: python
if not defined PY_EXE goto ERR_NO_PYTHON
if not exist "%PY_COLLECTOR%" goto ERR_NO_PY_SCRIPT

echo [INFO] Running Python collector.
pushd "%ROOT%" >nul
"%PY_EXE%" %PY_ARGS% "%PY_COLLECTOR%" --project-root "%ROOT%" --output-root "%ROOT%" %CLEAN_ARG% %PASS_ARGS%
set "RC=%errorlevel%"
popd >nul
goto DONE

:ERR_NO_PYTHON
echo [ERROR] Python was not found for the Python collector.
echo [INFO] Expected portable path:
echo %ROOT%\runtime\python.exe
set "RC=1"
goto DONE

:ERR_NO_PY_SCRIPT
echo [ERROR] Python collector script was not found.
echo [INFO] Expected path:
echo %PY_COLLECTOR%
set "RC=1"
goto DONE

:DONE
echo.
if "%RC%"=="0" (
    echo [OK] licenses\THIRD_PARTY_NOTICES.md and licenses\ were updated using python engine.
) else (
    echo [ERROR] Third-party license collection failed with exit code %RC%.
)
if not defined NO_PAUSE pause
exit /b %RC%
