@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Get - Install Portable 7-Zip

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "DL=%ROOT%\install\download"
set "SEVENZIP_DIR=%ROOT%\tools\7zip"
set "SEVENZIP_BIN=%ROOT%\tools\7zip\bin"
set "TMP=%ROOT%\system_core\_7zip_tmp"
set "EXTRACT=%TMP%\extra"
set "SEVENZR=%DL%\7zr.exe"
set "EXTRA=%DL%\7zip-extra.7z"
set "PS_EXE="
set "NO_PAUSE=0"

if /I "%~1"=="/NOPAUSE" set "NO_PAUSE=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%AUDION_NO_PAUSE%"=="1" set "NO_PAUSE=1"

if exist "%ROOT%\system_core\powershell\pwsh.exe" set "PS_EXE=%ROOT%\system_core\powershell\pwsh.exe"
if not defined PS_EXE where pwsh.exe >nul 2>nul && set "PS_EXE=pwsh.exe"
if not defined PS_EXE where powershell.exe >nul 2>nul && set "PS_EXE=powershell.exe"

if not exist "%DL%\" mkdir "%DL%" >nul 2>nul
if not exist "%SEVENZIP_BIN%\" mkdir "%SEVENZIP_BIN%" >nul 2>nul

echo ======================================================================
echo   AUDION GET - INSTALL PORTABLE 7-ZIP
echo ======================================================================
echo Root:    %ROOT%
echo Target:  %SEVENZIP_BIN%
echo DL:      %DL%
echo PS:      %PS_EXE%
echo.

if not defined PS_EXE goto ERR_POWERSHELL

echo [1/4] Resolving latest 7-Zip release and downloading assets...
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$ProgressPreference='SilentlyContinue';" ^
  "$headers=@{'User-Agent'='Audion-Get'}; if($env:GITHUB_TOKEN){$headers['Authorization']='Bearer '+$env:GITHUB_TOKEN};" ^
  "$repo='https://github.com/ip7z/7zip'; $api='https://api.github.com/repos/ip7z/7zip/releases/latest'; $tag=$null; $zrUrl=$null; $extraUrl=$null; $downloaded=$false;" ^
  "try { $resp=$null; try { $resp=Invoke-WebRequest -Uri ($repo + '/releases/latest') -Headers $headers -MaximumRedirection 0 -ErrorAction Stop } catch { $resp=$_.Exception.Response }; $loc=$null; if($resp){ if($resp.Headers.Location){ $loc=[string]$resp.Headers.Location } elseif($resp.Headers['Location']){ $loc=[string]$resp.Headers['Location'] } }; if(-not $loc -or $loc -notmatch '/tag/(?<tag>[^/]+)$'){ throw 'Could not resolve latest 7-Zip release tag without API.' }; $tag=$Matches.tag; $assetStem=$tag.Replace('.',''); $zrUrl=($repo + '/releases/download/' + $tag + '/7zr.exe'); $extraUrl=($repo + '/releases/download/' + $tag + '/7z' + $assetStem + '-extra.7z'); Write-Host ('[INFO] Resolved through releases/latest redirect: ' + $tag) } catch { Write-Host ('[WARN] releases/latest resolver unavailable, using GitHub API: ' + $_.Exception.Message) };" ^
  "if($zrUrl -and $extraUrl){ try { Write-Host ('[URL] ' + $zrUrl); Invoke-WebRequest -Headers $headers -Uri $zrUrl -OutFile '%SEVENZR%'; Write-Host ('[URL] ' + $extraUrl); Invoke-WebRequest -Headers $headers -Uri $extraUrl -OutFile '%EXTRA%'; $downloaded=$true; Write-Host '[INFO] Direct release downloads succeeded.' } catch { Write-Host ('[WARN] Direct asset URL failed, using GitHub API: ' + $_.Exception.Message); $zrUrl=$null; $extraUrl=$null; Remove-Item -LiteralPath '%SEVENZR%','%EXTRA%' -Force -ErrorAction SilentlyContinue } };" ^
  "if(-not $zrUrl -or -not $extraUrl){ try { $r=Invoke-RestMethod -Headers $headers $api; $tag=$r.tag_name; $zrUrl=$null; $extraUrl=$null; foreach($item in $r.assets){ if($item.name -eq '7zr.exe'){ $zrUrl=$item.browser_download_url }; if($item.name -like '7z*-extra.7z'){ $extraUrl=$item.browser_download_url } }; if(-not $zrUrl -or -not $extraUrl){ throw 'Required 7-Zip assets were not found.' }; Write-Host '[INFO] Resolved through GitHub API fallback.' } catch { throw ('Unable to resolve latest 7-Zip release: ' + $_.Exception.Message) } };" ^
  "Write-Host ('[VER] ' + $tag);" ^
  "Write-Host ('[URL] ' + $zrUrl);" ^
  "if(-not $downloaded){ Invoke-WebRequest -Headers $headers -Uri $zrUrl -OutFile '%SEVENZR%' };" ^
  "Write-Host ('[URL] ' + $extraUrl);" ^
  "if(-not $downloaded){ Invoke-WebRequest -Headers $headers -Uri $extraUrl -OutFile '%EXTRA%' }"
if errorlevel 1 goto ERR_DOWNLOAD

if not exist "%SEVENZR%" goto ERR_DOWNLOAD
if not exist "%EXTRA%" goto ERR_DOWNLOAD
for %%F in ("%SEVENZR%") do echo [OK] Downloaded 7zr.exe: %%~zF bytes
for %%F in ("%EXTRA%") do echo [OK] Downloaded extra pack: %%~zF bytes
echo.

echo [2/4] Extracting 7-Zip extra pack...
if exist "%TMP%" rd /s /q "%TMP%" >nul 2>nul
mkdir "%EXTRACT%" >nul 2>nul

"%SEVENZR%" x "%EXTRA%" "-o%EXTRACT%" -y
if errorlevel 1 goto ERR_EXTRACT

if not exist "%EXTRACT%\7za.exe" goto ERR_NOEXE

echo [3/4] Copying binaries...
call :RESET_DIR "%SEVENZIP_DIR%"
if errorlevel 1 goto ERR_COPY
mkdir "%SEVENZIP_BIN%" >nul 2>nul
if not exist "%SEVENZIP_BIN%\" goto ERR_COPY
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "Copy-Item '%EXTRACT%\*' '%SEVENZIP_BIN%\' -Recurse -Force"
if errorlevel 1 goto ERR_COPY

copy /y "%SEVENZR%" "%SEVENZIP_BIN%\7zr.exe" >nul
if errorlevel 1 goto ERR_COPY

echo [4/4] Verifying...
"%SEVENZIP_BIN%\7za.exe" i | more +0
if errorlevel 1 goto ERR_VERIFY

rd /s /q "%TMP%" >nul 2>nul

echo.
echo [SUCCESS] 7-Zip installed: %SEVENZIP_BIN%
call :PAUSE_IF_NEEDED
exit /b 0

:ERR_POWERSHELL
echo [ERROR] PowerShell was not found.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_DOWNLOAD
echo [ERROR] 7-Zip download failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_EXTRACT
echo [ERROR] 7-Zip extract failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_NOEXE
echo [ERROR] 7za.exe was not found after extraction.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_COPY
echo [ERROR] Copy to tools\7zip\bin failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_VERIFY
echo [ERROR] 7-Zip verification failed.
call :PAUSE_IF_NEEDED
exit /b 1

:RESET_DIR
set "TARGET_DIR=%~1"
if not defined TARGET_DIR exit /b 1
if /I not "%TARGET_DIR%"=="%SEVENZIP_DIR%" exit /b 1
if exist "%TARGET_DIR%\" rd /s /q "%TARGET_DIR%" >nul 2>nul
mkdir "%TARGET_DIR%" >nul 2>nul
if not exist "%TARGET_DIR%\" exit /b 1
exit /b 0

:PAUSE_IF_NEEDED
if not "%NO_PAUSE%"=="1" pause
goto :eof
