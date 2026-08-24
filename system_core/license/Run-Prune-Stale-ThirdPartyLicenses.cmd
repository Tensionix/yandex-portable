@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Portable Template - Prune Stale Third-Party Licenses

set "NO_PAUSE="
set "PASS_ARGS="
:ARG_LOOP
if "%~1"=="" goto ARGS_DONE
if /I "%~1"=="/NOPAUSE" (
    set "NO_PAUSE=1"
    shift
    goto ARG_LOOP
)
set "PASS_ARGS=%PASS_ARGS% %~1"
shift
goto ARG_LOOP
:ARGS_DONE

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
if not exist "%SCRIPT_DIR%\prune_stale_collected_licenses.py" (
    if exist "%CD%\system_core\license\prune_stale_collected_licenses.py" (
        set "SCRIPT_DIR=%CD%\system_core\license"
    ) else if exist "%CD%\prune_stale_collected_licenses.py" (
        set "SCRIPT_DIR=%CD%"
    )
)
for %%A in ("%SCRIPT_DIR%\..\..") do set "ROOT=%%~fA"
if not exist "%ROOT%\system_core\license\prune_stale_collected_licenses.py" (
    if exist "%CD%\system_core\license\prune_stale_collected_licenses.py" set "ROOT=%CD%"
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

echo [ERROR] Python was not found for stale license pruning.
if not defined NO_PAUSE pause
exit /b 1

:PY_READY
"%PY_EXE%" %PY_ARGS% "%SCRIPT_DIR%\prune_stale_collected_licenses.py" --project-root "%ROOT%" --output-root "%ROOT%" %PASS_ARGS%
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
    echo [OK] Stale collected license folders were pruned.
) else (
    echo [ERROR] Stale license pruning failed with exit code %RC%.
)
if not defined NO_PAUSE pause
exit /b %RC%
