@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "BASE_DIR=%~dp0.."
for %%I in ("%BASE_DIR%") do set "BASE_DIR=%%~fI"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BASE_DIR%\install\Build-StartLauncher.ps1" %*
exit /b %ERRORLEVEL%
