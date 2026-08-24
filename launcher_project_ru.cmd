@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion Yandex Portable - Project Launcher RU

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "CORE_DIR=%BASE_DIR%\system_core"
set "INSTALL_DIR=%BASE_DIR%\install"
set "FZF_EXE=%CORE_DIR%\fzf.exe"
set "RUNTIME_DIR=%BASE_DIR%\._runtime"
set "MENU_FILE=%RUNTIME_DIR%\project_menu_ru.txt"
set "RES_FILE=%RUNTIME_DIR%\project_menu_ru_res.txt"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul

call :RESOLVE_PYTHON
if errorlevel 1 goto NO_PYTHON

:MAIN
cls
echo ======================================================================
echo   AUDION PYTHON GUI PORTABLE TEMPLATE - РУССКИЙ ЛАУНЧЕР ПРОЕКТА
echo ======================================================================
echo Root:   %BASE_DIR%
echo Python: %PYTHON_CMD% %PYTHON_ARGS%
echo.

if exist "%FZF_EXE%" goto FZF_MENU
goto FALLBACK_MENU

:FZF_MENU
> "%MENU_FILE%" echo [01] ЗАПУСТИТЬ ОСНОВНОЙ СКРИПТ     ^| run_main            ^| system_core\main.py
>>"%MENU_FILE%" echo [02] ПРОВЕРИТЬ ОКРУЖЕНИЕ             ^| run_doctor          ^| runtime and imports
>>"%MENU_FILE%" echo [03] MD TABLE INSPECTOR              ^| run_table_inspector ^| inspect broken markdown tables
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [04] СОБРАТЬ PORTABLE ENV CMD        ^| build_cmd           ^| rebuild runtime via CMD builder
>>"%MENU_FILE%" echo [05] СОБРАТЬ PORTABLE ENV PS         ^| build_ps            ^| optional PowerShell builder
>>"%MENU_FILE%" echo [06] УСТАНОВИТЬ PORTABLE OFFLINE     ^| install_offline     ^| local runtime plus wheelhouse
>>"%MENU_FILE%" echo [07] ПРОВЕРИТЬ PORTABLE ENV          ^| verify_env          ^| run doctor
>>"%MENU_FILE%" echo [08] ОБНОВИТЬ FZF                    ^| update_fzf          ^| download latest fzf.exe
>>"%MENU_FILE%" echo [09] СОБРАТЬ RELEASE ARCHIVE         ^| make_release        ^| zip project
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [10] ОТКРЫТЬ INPUT                   ^| open_input          ^| explorer input
>>"%MENU_FILE%" echo [11] ОТКРЫТЬ OUTPUT                  ^| open_output         ^| explorer output
>>"%MENU_FILE%" echo [12] ОТКРЫТЬ LOGS                    ^| open_logs           ^| explorer logs
>>"%MENU_FILE%" echo [13] TOOLS LAUNCHER                  ^| tools               ^| open utility launcher
>>"%MENU_FILE%" echo [14] ENGLISH PROJECT LAUNCHER        ^| launcher_en         ^| open English launcher
>>"%MENU_FILE%" echo [00] ВЫХОД                           ^| exit                ^| close

type "%MENU_FILE%" | "%FZF_EXE%" --prompt="audion@portable-template [PROJECT RU] > " --pointer=">" --header="Выберите действие:" --layout=reverse --border="rounded" --info=hidden --margin=1,2 > "%RES_FILE%"

set "CHOICE="
set /p CHOICE=<"%RES_FILE%"
if not defined CHOICE goto MAIN

for /f "tokens=2 delims=|" %%a in ("%CHOICE%") do set "RAW=%%a"
call :TRIM RAW

if /I "%RAW%"=="run_main" goto RUN_MAIN
if /I "%RAW%"=="run_doctor" goto RUN_DOCTOR
if /I "%RAW%"=="run_table_inspector" goto RUN_TABLE_INSPECTOR
if /I "%RAW%"=="build_cmd" goto BUILD_CMD
if /I "%RAW%"=="build_ps" goto BUILD_PS
if /I "%RAW%"=="install_offline" goto INSTALL_OFFLINE
if /I "%RAW%"=="verify_env" goto VERIFY_ENV
if /I "%RAW%"=="update_fzf" goto UPDATE_FZF
if /I "%RAW%"=="make_release" goto MAKE_RELEASE
if /I "%RAW%"=="open_input" goto OPEN_INPUT
if /I "%RAW%"=="open_output" goto OPEN_OUTPUT
if /I "%RAW%"=="open_logs" goto OPEN_LOGS
if /I "%RAW%"=="tools" goto TOOLS
if /I "%RAW%"=="launcher_en" goto LAUNCHER_EN
if /I "%RAW%"=="exit" exit /b 0
goto MAIN

:FALLBACK_MENU
echo [1] Запустить основной скрипт
echo [2] Проверить окружение
echo [3] MD table inspector
echo [4] Собрать portable env CMD builder
echo [5] Собрать portable env PS
echo [6] Установить portable offline
echo [7] Проверить portable env
echo [8] Обновить fzf
echo [9] Собрать release archive
echo [A] Открыть input
echo [B] Открыть output
echo [C] Открыть logs
echo [T] Tools launcher
echo [E] English project launcher
echo [0] Выход
echo.
choice /C 123456789ABCTE0 /N /M "Select: "
if errorlevel 15 exit /b 0
if errorlevel 14 goto LAUNCHER_EN
if errorlevel 13 goto TOOLS
if errorlevel 12 goto OPEN_LOGS
if errorlevel 11 goto OPEN_OUTPUT
if errorlevel 10 goto OPEN_INPUT
if errorlevel 9 goto MAKE_RELEASE
if errorlevel 8 goto UPDATE_FZF
if errorlevel 7 goto VERIFY_ENV
if errorlevel 6 goto INSTALL_OFFLINE
if errorlevel 5 goto BUILD_PS
if errorlevel 4 goto BUILD_CMD
if errorlevel 3 goto RUN_TABLE_INSPECTOR
if errorlevel 2 goto RUN_DOCTOR
if errorlevel 1 goto RUN_MAIN
goto MAIN

:RUN_MAIN
call :RUNPY "%CORE_DIR%\main.py"
pause
goto MAIN

:RUN_DOCTOR
call :RUNPY "%CORE_DIR%\doctor.py"
pause
goto MAIN

:RUN_TABLE_INSPECTOR
echo.
set "MD_NAME="
set /p MD_NAME=Файл в папке input\ : 
if not defined MD_NAME goto MAIN
call :RUNPY "%CORE_DIR%\inspect_md_tables.py" --input "%BASE_DIR%\input\%MD_NAME%"
pause
goto MAIN

:BUILD_CMD
call "%INSTALL_DIR%\Build_Portable_Env_Build.cmd"
goto MAIN

:BUILD_PS
call "%INSTALL_DIR%\Build_Portable_Env.cmd"
goto MAIN

:INSTALL_OFFLINE
call "%INSTALL_DIR%\install_portable_offline.cmd"
goto MAIN

:VERIFY_ENV
call "%INSTALL_DIR%\verify_portable_env.cmd"
goto MAIN

:UPDATE_FZF
call "%INSTALL_DIR%\launcher-tools-update_fzf.cmd"
goto MAIN

:MAKE_RELEASE
call "%INSTALL_DIR%\make_release_archive.cmd"
goto MAIN

:OPEN_INPUT
start "" explorer "%BASE_DIR%\input"
goto MAIN

:OPEN_OUTPUT
start "" explorer "%BASE_DIR%\output"
goto MAIN

:OPEN_LOGS
start "" explorer "%BASE_DIR%\logs"
goto MAIN

:TOOLS
call "%BASE_DIR%\launcher_tools.cmd"
goto MAIN

:LAUNCHER_EN
call "%BASE_DIR%\launcher_project.cmd"
goto MAIN

:NO_PYTHON
cls
echo [ОШИБКА] Python runtime не найден.
echo.
echo Поддерживаемые варианты:
echo   runtime\python.exe
echo   runtime\python\python.exe
echo   py -3.12
echo   python
echo.
echo Используйте builder_main.cmd или install\Build_Portable_Env_Build.cmd
pause
exit /b 1

:RUNPY
set "TARGET=%~1"
shift
if exist "%TARGET%" goto RUNPY_OK
echo [ОШИБКА] Скрипт не найден:
echo %TARGET%
goto :eof
:RUNPY_OK
"%PYTHON_CMD%" %PYTHON_ARGS% "%TARGET%" %*
goto :eof

:RESOLVE_PYTHON
set "PYTHON_CMD="
set "PYTHON_ARGS="

if exist "%BASE_DIR%\runtime\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python.exe"
  goto PY_OK
)

if exist "%BASE_DIR%\runtime\python\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python\python.exe"
  goto PY_OK
)

py -3.12 -V >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
  set "PYTHON_ARGS=-3.12"
  goto PY_OK
)

where python >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  goto PY_OK
)

exit /b 1

:PY_OK
exit /b 0

:TRIM
for /f "tokens=* delims= " %%z in ("!%~1!") do set "%~1=%%z"
:TRIM_R
if "!%~1:~-1!"==" " set "%~1=!%~1:~0,-1!" & goto TRIM_R
goto :eof
