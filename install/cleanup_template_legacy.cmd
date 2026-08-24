@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Audion Yandex Portable - Legacy Cleaner

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "PS_EXE="
if exist "%ROOT%\system_core\powershell\pwsh.exe" set "PS_EXE=%ROOT%\system_core\powershell\pwsh.exe"
if not defined PS_EXE where pwsh.exe >nul 2>nul && set "PS_EXE=pwsh.exe"
if not defined PS_EXE where powershell.exe >nul 2>nul && set "PS_EXE=powershell.exe"

if not defined PS_EXE (
  echo [ERROR] PowerShell was not found.
  echo Expected portable path:
  echo   %ROOT%\system_core\powershell\pwsh.exe
  pause
  exit /b 1
)

echo ======================================================================
echo   AUDION PYTHON GUI PORTABLE TEMPLATE - LEGACY CLEANER
echo ======================================================================
echo This cleaner is safe by default:
echo   - no arguments: dry-run only
echo   - -Apply: archives unreferenced historical files into docs\archive
echo   - language-specific RU/EN launchers are protected
echo.

"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\Clean-TemplateLegacy.ps1" -Root "%ROOT%" %*
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
  echo [OK] Legacy cleaner finished.
) else (
  echo [ERROR] Legacy cleaner failed with exit code %RC%.
)

pause
exit /b %RC%
