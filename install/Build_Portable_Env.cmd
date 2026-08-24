@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "PS_EXE="
set "PS1_FILE=%~dpn0.ps1"

if exist "%~dp0..\system_core\powershell\pwsh.exe" set "PS_EXE=%~dp0..\system_core\powershell\pwsh.exe"
if not defined PS_EXE where pwsh.exe >nul 2>nul && set "PS_EXE=pwsh.exe"
if not defined PS_EXE where powershell.exe >nul 2>nul && set "PS_EXE=powershell.exe"

if not defined PS_EXE (
    echo [ERROR] PowerShell was not found.
    echo [INFO] Expected portable path:
    echo %~dp0..\system_core\powershell\pwsh.exe
    pause
    exit /b 1
)

"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1_FILE%" %*
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
    echo [OK] Build_Portable_Env.ps1 finished successfully.
) else (
    echo [ERROR] Build_Portable_Env.ps1 finished with exit code %RC%.
)

pause
exit /b %RC%
