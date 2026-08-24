@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Yandex Portable - Builder

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "FZF_EXE=%BASE_DIR%\system_core\fzf.exe"
set "RUNTIME_DIR=%BASE_DIR%\._runtime"
set "MENU_FILE=%RUNTIME_DIR%\builder_menu.txt"
set "RES_FILE=%RUNTIME_DIR%\builder_menu_res.txt"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul

:MAIN
cls
echo ======================================================================
echo   AUDION YANDEX PORTABLE - BUILDER
echo ======================================================================
echo Root: %BASE_DIR%
echo.

if exist "%FZF_EXE%" goto FZF_MENU
goto FALLBACK_MENU

:FZF_MENU
> "%MENU_FILE%" echo [01] PYTHON ENV CMD                      ^| build_cmd        ^| main CMD build script
>>"%MENU_FILE%" echo [02] PYTHON ENV PS                       ^| build_ps         ^| optional PowerShell builder
>>"%MENU_FILE%" echo [03] FZF                                 ^| update_fzf       ^| install/update system_core\fzf.exe
>>"%MENU_FILE%" echo [04] POWERSHELL                          ^| install_pwsh     ^| optional pwsh for pickers/build helpers
>>"%MENU_FILE%" echo [05] START LAUNCHER                      ^| build_launcher   ^| rebuild Start.exe launcher
>>"%MENU_FILE%" echo [06] 7-ZIP                              ^| install_7zip     ^| portable 7za.exe, required to unpack browsers
>>"%MENU_FILE%" echo [09] PORTABLE OFFLINE                    ^| install_offline  ^| use local runtime and wheelhouse
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [70] CLEAN INSTALL CACHE                 ^| clean_cache      ^| clean install cache/staging/bytecode
>>"%MENU_FILE%" echo [71] VERIFY / DOCTOR                     ^| verify           ^| run doctor.py
>>"%MENU_FILE%" echo [72] CMD ENCODING CHECK                  ^| cmd_encoding     ^| UTF-8 no-BOM CRLF
>>"%MENU_FILE%" echo [73] UPDATE REQUIREMENTS LOCK            ^| update_req_lock  ^| compile requirements_lock.txt
>>"%MENU_FILE%" echo [74] COLLECT RELEASE LICENSES            ^| collect_licenses ^| run collection only before release
>>"%MENU_FILE%" echo [75] PRUNE STALE LICENSE FOLDERS         ^| prune_licenses   ^| remove folders for uninstalled packages
>>"%MENU_FILE%" echo [76] DEDUPLICATE LICENSE FILES           ^| dedupe_licenses  ^| cleanup exact duplicate texts
>>"%MENU_FILE%" echo [77] MAKE RELEASE ARCHIVE                ^| release          ^| stage, refresh licenses, create zip
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [90] PROJECT LAUNCHER                    ^| project          ^| open runtime menu
>>"%MENU_FILE%" echo [91] TEMPLATE LEGACY CLEANER             ^| legacy_clean     ^| dry-run source/doc cleanup policy
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [95] OPEN install                        ^| open_install     ^| explorer
>>"%MENU_FILE%" echo [96] OPEN runtime                        ^| open_runtime     ^| explorer
>>"%MENU_FILE%" echo [97] OPEN wheelhouse                     ^| open_wheels      ^| explorer
>>"%MENU_FILE%" echo [98] OPEN licenses                       ^| open_licenses    ^| explorer
>>"%MENU_FILE%" echo [99] OPEN release                        ^| open_release     ^| explorer
>>"%MENU_FILE%" echo [00] EXIT                                ^| exit             ^| close

type "%MENU_FILE%" | "%FZF_EXE%" --prompt="audion@portable-builder > " --pointer=">" --header="Pick step:" --layout=reverse --border="rounded" --info=hidden --margin=1,2 > "%RES_FILE%"

set "CHOICE="
set /p CHOICE=<"%RES_FILE%"
if not defined CHOICE goto MAIN

for /f "tokens=2 delims=|" %%a in ("%CHOICE%") do set "RAW=%%a"
call :TRIM RAW

if /I "%RAW%"=="build_cmd" goto BUILD_CMD
if /I "%RAW%"=="build_ps" goto BUILD_PS
if /I "%RAW%"=="update_fzf" goto UPDATE_FZF
if /I "%RAW%"=="install_pwsh" goto INSTALL_PWSH
if /I "%RAW%"=="build_launcher" goto BUILD_LAUNCHER
if /I "%RAW%"=="install_7zip" goto INSTALL_7ZIP
if /I "%RAW%"=="install_offline" goto INSTALL_OFFLINE
if /I "%RAW%"=="clean_cache" goto CLEAN_CACHE
if /I "%RAW%"=="verify" goto VERIFY
if /I "%RAW%"=="cmd_encoding" goto CMD_ENCODING
if /I "%RAW%"=="update_req_lock" goto UPDATE_REQ_LOCK
if /I "%RAW%"=="collect_licenses" goto COLLECT_LICENSES
if /I "%RAW%"=="prune_licenses" goto PRUNE_LICENSES
if /I "%RAW%"=="dedupe_licenses" goto DEDUPE_LICENSES
if /I "%RAW%"=="release" goto RELEASE
if /I "%RAW%"=="project" goto PROJECT
if /I "%RAW%"=="legacy_clean" goto LEGACY_CLEAN
if /I "%RAW%"=="open_install" goto OPEN_INSTALL
if /I "%RAW%"=="open_runtime" goto OPEN_RUNTIME
if /I "%RAW%"=="open_wheels" goto OPEN_WHEELS
if /I "%RAW%"=="open_licenses" goto OPEN_LICENSES
if /I "%RAW%"=="open_release" goto OPEN_RELEASE
if /I "%RAW%"=="exit" exit /b 0
goto MAIN

:FALLBACK_MENU
echo [01] PYTHON ENV CMD
echo [02] PYTHON ENV PS
echo [03] FZF
echo [04] POWERSHELL
echo [05] START LAUNCHER
echo [06] 7-ZIP
echo [09] PORTABLE OFFLINE
echo.
echo [70] CLEAN INSTALL CACHE
echo [71] VERIFY / DOCTOR
echo [72] CMD ENCODING CHECK
echo [73] UPDATE REQUIREMENTS LOCK
echo [74] COLLECT RELEASE LICENSES
echo [75] PRUNE STALE LICENSE FOLDERS
echo [76] DEDUPLICATE LICENSE FILES
echo [77] MAKE RELEASE ARCHIVE
echo.
echo [90] PROJECT LAUNCHER
echo [91] TEMPLATE LEGACY CLEANER
echo.
echo [95] OPEN install
echo [96] OPEN runtime
echo [97] OPEN wheelhouse
echo [98] OPEN licenses
echo [99] OPEN release
echo.
echo [00] EXIT
echo.
set "RAW="
set /p RAW="Select step number or id: "
call :TRIM RAW
if not defined RAW goto MAIN
if /I "%RAW%"=="01" goto BUILD_CMD
if /I "%RAW%"=="1" goto BUILD_CMD
if /I "%RAW%"=="build_cmd" goto BUILD_CMD
if /I "%RAW%"=="02" goto BUILD_PS
if /I "%RAW%"=="2" goto BUILD_PS
if /I "%RAW%"=="build_ps" goto BUILD_PS
if /I "%RAW%"=="03" goto UPDATE_FZF
if /I "%RAW%"=="3" goto UPDATE_FZF
if /I "%RAW%"=="update_fzf" goto UPDATE_FZF
if /I "%RAW%"=="04" goto INSTALL_PWSH
if /I "%RAW%"=="4" goto INSTALL_PWSH
if /I "%RAW%"=="install_pwsh" goto INSTALL_PWSH
if /I "%RAW%"=="05" goto BUILD_LAUNCHER
if /I "%RAW%"=="5" goto BUILD_LAUNCHER
if /I "%RAW%"=="build_launcher" goto BUILD_LAUNCHER
if /I "%RAW%"=="Build-StartLauncher" goto BUILD_LAUNCHER
if /I "%RAW%"=="06" goto INSTALL_7ZIP
if /I "%RAW%"=="6" goto INSTALL_7ZIP
if /I "%RAW%"=="install_7zip" goto INSTALL_7ZIP
if /I "%RAW%"=="Build-StartLauncher.cmd" goto BUILD_LAUNCHER
if /I "%RAW%"=="09" goto INSTALL_OFFLINE
if /I "%RAW%"=="9" goto INSTALL_OFFLINE
if /I "%RAW%"=="install_offline" goto INSTALL_OFFLINE
if /I "%RAW%"=="70" goto CLEAN_CACHE
if /I "%RAW%"=="clean_cache" goto CLEAN_CACHE
if /I "%RAW%"=="71" goto VERIFY
if /I "%RAW%"=="verify" goto VERIFY
if /I "%RAW%"=="72" goto CMD_ENCODING
if /I "%RAW%"=="cmd_encoding" goto CMD_ENCODING
if /I "%RAW%"=="73" goto UPDATE_REQ_LOCK
if /I "%RAW%"=="update_req_lock" goto UPDATE_REQ_LOCK
if /I "%RAW%"=="Update-Requirements-Lock" goto UPDATE_REQ_LOCK
if /I "%RAW%"=="Update-Requirements-Lock.cmd" goto UPDATE_REQ_LOCK
if /I "%RAW%"=="74" goto COLLECT_LICENSES
if /I "%RAW%"=="collect_licenses" goto COLLECT_LICENSES
if /I "%RAW%"=="75" goto PRUNE_LICENSES
if /I "%RAW%"=="prune_licenses" goto PRUNE_LICENSES
if /I "%RAW%"=="76" goto DEDUPE_LICENSES
if /I "%RAW%"=="dedupe_licenses" goto DEDUPE_LICENSES
if /I "%RAW%"=="77" goto RELEASE
if /I "%RAW%"=="release" goto RELEASE
if /I "%RAW%"=="90" goto PROJECT
if /I "%RAW%"=="project" goto PROJECT
if /I "%RAW%"=="91" goto LEGACY_CLEAN
if /I "%RAW%"=="legacy_clean" goto LEGACY_CLEAN
if /I "%RAW%"=="95" goto OPEN_INSTALL
if /I "%RAW%"=="open_install" goto OPEN_INSTALL
if /I "%RAW%"=="96" goto OPEN_RUNTIME
if /I "%RAW%"=="open_runtime" goto OPEN_RUNTIME
if /I "%RAW%"=="97" goto OPEN_WHEELS
if /I "%RAW%"=="open_wheels" goto OPEN_WHEELS
if /I "%RAW%"=="98" goto OPEN_LICENSES
if /I "%RAW%"=="open_licenses" goto OPEN_LICENSES
if /I "%RAW%"=="99" goto OPEN_RELEASE
if /I "%RAW%"=="open_release" goto OPEN_RELEASE
if /I "%RAW%"=="00" exit /b 0
if /I "%RAW%"=="0" exit /b 0
if /I "%RAW%"=="exit" exit /b 0
goto MAIN

:BUILD_CMD
call "%BASE_DIR%\install\Build_Portable_Env_Build.cmd"
goto MAIN

:BUILD_PS
call "%BASE_DIR%\install\Build_Portable_Env.cmd"
goto MAIN

:INSTALL_PWSH
call "%BASE_DIR%\install\Install-Portable-PowerShell.cmd"
goto MAIN

:BUILD_LAUNCHER
call "%BASE_DIR%\install\Build-StartLauncher.cmd"
goto MAIN

:UPDATE_FZF
call "%BASE_DIR%\install\launcher-tools-update_fzf.cmd"
goto MAIN

:INSTALL_7ZIP
call "%BASE_DIR%\install\Install-Portable-7Zip.cmd"

:INSTALL_OFFLINE
call "%BASE_DIR%\install\install_portable_offline.cmd"
goto MAIN

:CLEAN_CACHE
call "%BASE_DIR%\install\Clean-Install-Cache.cmd"
goto MAIN

:VERIFY
call "%BASE_DIR%\install\verify_portable_env.cmd"
goto MAIN

:CMD_ENCODING
powershell -NoProfile -ExecutionPolicy Bypass -File "%BASE_DIR%\install\Repair-CmdEncoding.ps1" -Root "%BASE_DIR%" -Fix
set "RC=%errorlevel%"
echo.
echo [INFO] CMD encoding repair finished with exit code %RC%.
echo [INFO] Restart builder_main.cmd before continuing.
pause
exit /b %RC%

:UPDATE_REQ_LOCK
call "%BASE_DIR%\install\Update-Requirements-Lock.cmd"
goto MAIN

:COLLECT_LICENSES
call "%BASE_DIR%\system_core\license\Run-Collect-ThirdPartyLicenses.cmd"
goto MAIN

:PRUNE_LICENSES
call "%BASE_DIR%\system_core\license\Run-Prune-Stale-ThirdPartyLicenses.cmd"
goto MAIN

:DEDUPE_LICENSES
call "%BASE_DIR%\system_core\license\Run-Deduplicate-ThirdPartyLicenses.cmd"
goto MAIN

:RELEASE
call "%BASE_DIR%\install\make_release_archive.cmd"
goto MAIN

:OPEN_INSTALL
start "" explorer "%BASE_DIR%\install"
goto MAIN

:OPEN_RUNTIME
start "" explorer "%BASE_DIR%\runtime"
goto MAIN

:OPEN_WHEELS
start "" explorer "%BASE_DIR%\wheelhouse"
goto MAIN

:OPEN_LICENSES
if not exist "%BASE_DIR%\licenses" mkdir "%BASE_DIR%\licenses" >nul 2>nul
start "" explorer "%BASE_DIR%\licenses"
goto MAIN

:OPEN_RELEASE
start "" explorer "%BASE_DIR%\release"
goto MAIN

:PROJECT
call "%BASE_DIR%\launcher_project.cmd"
goto MAIN

:LEGACY_CLEAN
call "%BASE_DIR%\install\cleanup_template_legacy.cmd"
goto MAIN

:TRIM
for /f "tokens=* delims= " %%z in ("!%~1!") do set "%~1=%%z"
:TRIM_R
if "!%~1:~-1!"==" " set "%~1=!%~1:~0,-1!" & goto TRIM_R
goto :eof

