@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "PS1_FILE=%SCRIPT_DIR%\Repair-CmdEncoding.ps1"
if not exist "%PS1_FILE%" goto ERR_HELPER

set "PS_EXE="
if exist "%ROOT%\system_core\powershell\pwsh.exe" set "PS_EXE=%ROOT%\system_core\powershell\pwsh.exe"
if not defined PS_EXE (
  where pwsh.exe >nul 2>nul
  if not errorlevel 1 set "PS_EXE=pwsh.exe"
)
if not defined PS_EXE (
  where powershell.exe >nul 2>nul
  if not errorlevel 1 set "PS_EXE=powershell.exe"
)

if not defined PS_EXE goto ERR_POWERSHELL

"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1_FILE%" -Root "%ROOT%" %*
exit /b %errorlevel%

:ERR_HELPER
echo [ERROR] Repair-CmdEncoding.ps1 was not found.
exit /b 1

:ERR_POWERSHELL
echo [ERROR] PowerShell was not found for CMD encoding check.
exit /b 1
