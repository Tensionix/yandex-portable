@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion Python Portable Template - Build Portable Env

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "INSTALL_DIR=%ROOT%\install"
set "DOWNLOAD_DIR=%INSTALL_DIR%\download"
set "RUNTIME_DIR=%ROOT%\runtime"
set "WHEELHOUSE_DIR=%ROOT%\wheelhouse"
set "REQ_FILE=%INSTALL_DIR%\requirements_full.in"
set "DOCTOR=%ROOT%\system_core\doctor.py"
set "GUI_APP=%ROOT%\system_core\ui_nicegui\app.py"
set "GET_PIP=%DOWNLOAD_DIR%\get-pip.py"

set "PYTHON_MINOR=12"
for /f "usebackq delims=" %%V in (`powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $latest=$null; for($i=0; $i -le 40; $i++){ $v='3.%PYTHON_MINOR%.'+$i; $u='https://www.python.org/ftp/python/'+$v+'/python-'+$v+'-embed-amd64.zip'; try{ Invoke-WebRequest -Uri $u -Method Head -TimeoutSec 10 | Out-Null; $latest=$v } catch { if($latest){ break } } }; if(-not $latest){ exit 1 }; $latest"`) do set "PYTHON_VERSION=%%V"
if not defined PYTHON_VERSION goto USE_POWERSHELL
set "PYTHON_ZIP=python-%PYTHON_VERSION%-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_ZIP%"
set "PYTHON_ZIP_PATH=%DOWNLOAD_DIR%\%PYTHON_ZIP%"

call "%INSTALL_DIR%\init_folders.cmd"

echo ======================================================================
echo   AUDION PYTHON PORTABLE TEMPLATE - BUILD PORTABLE ENV
echo ======================================================================
echo Root:       %ROOT%
echo Install:    %INSTALL_DIR%
echo Download:   %DOWNLOAD_DIR%
echo Runtime:    %RUNTIME_DIR%
echo Wheelhouse: %WHEELHOUSE_DIR%
echo.

if not exist "%REQ_FILE%" goto ERR_REQ

where curl.exe >nul 2>nul
if errorlevel 1 goto USE_POWERSHELL

where tar.exe >nul 2>nul
if errorlevel 1 goto USE_POWERSHELL

echo [1/6] Downloading Python Embedded...
curl.exe -L --fail --retry 5 --connect-timeout 30 -o "%PYTHON_ZIP_PATH%" "%PYTHON_URL%"
if errorlevel 1 goto ERR_DOWNLOAD

echo [2/6] Extracting runtime...
if exist "%RUNTIME_DIR%\" rd /s /q "%RUNTIME_DIR%" >nul 2>nul
mkdir "%RUNTIME_DIR%" >nul 2>nul
tar.exe -xf "%PYTHON_ZIP_PATH%" -C "%RUNTIME_DIR%"
if errorlevel 1 goto USE_POWERSHELL

echo [3/6] Enabling import site...
call :PATCH_PTH "%RUNTIME_DIR%\python3%PYTHON_MINOR%._pth"
if errorlevel 1 goto ERR_PTH

echo [4/6] Downloading get-pip.py...
curl.exe -L --fail --retry 5 --connect-timeout 30 -o "%GET_PIP%" "https://bootstrap.pypa.io/get-pip.py"
if errorlevel 1 goto ERR_GETPIP

if not exist "%RUNTIME_DIR%\python.exe" goto ERR_PYTHON

echo [5/6] Installing pip...
"%RUNTIME_DIR%\python.exe" "%GET_PIP%"
if errorlevel 1 goto ERR_PIP

echo [6/6] Installing build bootstrap...
"%RUNTIME_DIR%\python.exe" -m pip install --disable-pip-version-check --upgrade setuptools wheel packaging
if errorlevel 1 goto ERR_INSTALL

echo [6/6] Building wheelhouse...
for /f "delims=" %%F in ('dir /a /b "%WHEELHOUSE_DIR%" 2^>nul') do (
  if exist "%WHEELHOUSE_DIR%\%%F\" (
    rd /s /q "%WHEELHOUSE_DIR%\%%F"
  ) else (
    del /f /q "%WHEELHOUSE_DIR%\%%F"
  )
)
"%RUNTIME_DIR%\python.exe" -m pip wheel --disable-pip-version-check --prefer-binary --no-build-isolation --timeout 120 --retries 12 -r "%REQ_FILE%" -w "%WHEELHOUSE_DIR%"
if errorlevel 1 goto ERR_WHEELS

echo [6/6] Installing packages from local wheelhouse...
"%RUNTIME_DIR%\python.exe" -m pip install --disable-pip-version-check --no-build-isolation --no-index --find-links="%WHEELHOUSE_DIR%" -r "%REQ_FILE%"
if errorlevel 1 goto ERR_INSTALL

echo [verify] Verifying environment...
"%RUNTIME_DIR%\python.exe" "%DOCTOR%" --project-root "%ROOT%"
if errorlevel 1 goto ERR_VERIFY
if exist "%GUI_APP%" (
  "%RUNTIME_DIR%\python.exe" "%GUI_APP%" --smoke
  if errorlevel 1 goto ERR_VERIFY
)

echo.
echo [SUCCESS] Portable environment is ready.
pause
exit /b 0

:USE_POWERSHELL
echo [INFO] CMD prerequisites are incomplete.
echo [INFO] Falling back to Build_Portable_Env.ps1
call "%INSTALL_DIR%\Build_Portable_Env.cmd"
exit /b %errorlevel%

:PATCH_PTH
set "PTH_FILE=%~1"
if not exist "%PTH_FILE%" exit /b 1
set "TMP_FILE=%PTH_FILE%.tmp"
break > "%TMP_FILE%"
for /f "usebackq delims=" %%L in ("%PTH_FILE%") do (
  set "LINE=%%L"
  if "!LINE!"=="#import site" (
    >>"%TMP_FILE%" echo import site
  ) else (
    >>"%TMP_FILE%" echo %%L
  )
)
move /y "%TMP_FILE%" "%PTH_FILE%" >nul
exit /b 0

:ERR_REQ
echo [ERROR] requirements_full.in was not found.
pause
exit /b 1

:ERR_DOWNLOAD
echo [ERROR] Failed to download Python Embedded ZIP.
pause
exit /b 1

:ERR_PTH
echo [ERROR] Failed to patch python3%PYTHON_MINOR%._pth
pause
exit /b 1

:ERR_GETPIP
echo [ERROR] Failed to download get-pip.py
pause
exit /b 1

:ERR_PYTHON
echo [ERROR] runtime\python.exe was not found after extraction.
pause
exit /b 1

:ERR_PIP
echo [ERROR] Failed to install pip into portable runtime.
pause
exit /b 1

:ERR_WHEELS
echo [ERROR] Failed to build wheelhouse.
pause
exit /b 1

:ERR_INSTALL
echo [ERROR] Failed to install packages from wheelhouse.
pause
exit /b 1

:ERR_VERIFY
echo [ERROR] Environment verification failed.
pause
exit /b 1

