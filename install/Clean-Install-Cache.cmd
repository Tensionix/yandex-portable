@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion - Clean Install Cache

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "PS1_FILE=%SCRIPT_DIR%\Clean-Install-Cache.ps1"
set "PS_EXE="
set "OPT_WHATIF="
set "OPT_SKIP_BYTECODE="
set "NO_PAUSE=0"

:ARG_LOOP
if "%~1"=="" goto ARGS_DONE
if /I "%~1"=="/DRY" set "OPT_WHATIF=-WhatIf"
if /I "%~1"=="/WHATIF" set "OPT_WHATIF=-WhatIf"
if /I "%~1"=="--dry-run" set "OPT_WHATIF=-WhatIf"
if /I "%~1"=="/NO-BYTECODE" set "OPT_SKIP_BYTECODE=-SkipBytecode"
if /I "%~1"=="--no-bytecode" set "OPT_SKIP_BYTECODE=-SkipBytecode"
if /I "%~1"=="/NOPAUSE" set "NO_PAUSE=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
shift
goto ARG_LOOP
:ARGS_DONE

rem Prefer a non-target PowerShell. Portable fallback is fine here because this
rem helper never replaces system_core\powershell.
where pwsh.exe >nul 2>nul && set "PS_EXE=pwsh.exe"
if not defined PS_EXE where powershell.exe >nul 2>nul && set "PS_EXE=powershell.exe"
if not defined PS_EXE if exist "%ROOT%\system_core\powershell\pwsh.exe" set "PS_EXE=%ROOT%\system_core\powershell\pwsh.exe"

if not defined PS_EXE goto ERR_NOPS
if not exist "%PS1_FILE%" goto ERR_NOPS1

echo ======================================================================
echo   AUDION - CLEAN INSTALL CACHE
echo ======================================================================
echo Project: %ROOT%
echo Targets: install\download\, system_core\_pwsh_tmp, system_core\_fzf_tmp, bytecode caches
if defined OPT_WHATIF echo Mode:    DRY-RUN ^(no files removed^)
if defined OPT_SKIP_BYTECODE echo Bytecode: skipped
echo.

"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1_FILE%" -ProjectRoot "%ROOT%" %OPT_WHATIF% %OPT_SKIP_BYTECODE%
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" goto ERR_RUN
echo [DONE] Install cache cleanup completed.
call :PAUSE_IF_NEEDED
exit /b 0

:ERR_NOPS
echo [ERROR] No PowerShell found.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_NOPS1
echo [ERROR] PS1 not found: %PS1_FILE%
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_RUN
echo [ERROR] Install cache cleanup failed ^(exit %RC%^).
call :PAUSE_IF_NEEDED
exit /b %RC%

:PAUSE_IF_NEEDED
if not "%NO_PAUSE%"=="1" pause
goto :eof
