@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion - Update FZF

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "DL=%ROOT%\install\download"
set "CORE=%ROOT%\system_core"
set "TMP=%CORE%\_fzf_tmp"
set "ZIP=%DL%\fzf_windows_amd64.zip"
set "PS_EXE="

where pwsh.exe >nul 2>nul && set "PS_EXE=pwsh.exe"
if not defined PS_EXE where powershell.exe >nul 2>nul && set "PS_EXE=powershell.exe"
if not defined PS_EXE if exist "%ROOT%\system_core\powershell\pwsh.exe" set "PS_EXE=%ROOT%\system_core\powershell\pwsh.exe"

if not exist "%DL%\" mkdir "%DL%" >nul 2>nul

echo ======================================================================
echo   AUDION - UPDATE FZF
echo ======================================================================
echo Root:    %ROOT%
echo Install: %SCRIPT_DIR%
echo DL:      %DL%
echo Core:    %CORE%
echo PS:      %PS_EXE%
echo.

if not defined PS_EXE goto ERR_POWERSHELL

echo [1/3] Resolving latest FZF and downloading ZIP...
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$zip='%ZIP%';" ^
  "$headers=@{'User-Agent'='Audion-FZF-Installer'}; if($env:GITHUB_TOKEN){$headers['Authorization']='Bearer '+$env:GITHUB_TOKEN};" ^
  "$repo='https://github.com/junegunn/fzf';" ^
  "$api='https://api.github.com/repos/junegunn/fzf/releases/latest';" ^
  "$url=$null; $tag=$null; $downloaded=$false;" ^
  "try { $resp=$null; try { $resp=Invoke-WebRequest -Uri ($repo + '/releases/latest') -Headers $headers -MaximumRedirection 0 -ErrorAction Stop } catch { $resp=$_.Exception.Response }; $loc=$null; if($resp){ if($resp.Headers.Location){ $loc=[string]$resp.Headers.Location } elseif($resp.Headers['Location']){ $loc=[string]$resp.Headers['Location'] } }; if(-not $loc){ throw 'Could not resolve latest fzf release tag without API.' }; if($loc -match '/tag/(?<tag>v?[0-9][^/]+)$'){ $tag=$Matches.tag } else { throw ('Unexpected latest redirect: ' + $loc) }; $version=$tag.TrimStart('v'); $url=($repo + '/releases/download/' + $tag + '/fzf-' + $version + '-windows_amd64.zip'); Write-Host ('[INFO] Resolved through releases/latest redirect: ' + $tag) } catch { Write-Host ('[WARN] releases/latest resolver unavailable, using GitHub API: ' + $_.Exception.Message) };" ^
  "if($url){ try { Write-Host ('[URL] ' + $url); Invoke-WebRequest -Uri $url -Headers $headers -OutFile $zip; $downloaded=$true; Write-Host '[INFO] Direct release download succeeded.' } catch { Write-Host ('[WARN] Direct asset URL failed, using GitHub API: ' + $_.Exception.Message); $url=$null; Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue } };" ^
  "if(-not $url){ try { $r=Invoke-RestMethod -Headers $headers $api; $tag=$r.tag_name; $a=$null; foreach($item in $r.assets){ if($item.name -like '*windows_amd64.zip'){ $a=$item; break } }; if(-not $a){ throw 'Asset not found: *windows_amd64.zip' }; $url=($a.browser_download_url).Trim(); Write-Host '[INFO] Resolved through GitHub API fallback.' } catch { throw ('Unable to resolve latest fzf release: ' + $_.Exception.Message) } };" ^
  "Write-Host ('[URL] ' + $url);" ^
  "if($tag){ Write-Host ('[VER] ' + $tag) };" ^
  "if(-not $downloaded){ Invoke-WebRequest -Uri $url -Headers $headers -OutFile $zip }"
if errorlevel 1 goto ERR_DOWNLOAD

if not exist "%ZIP%" goto ERR_DOWNLOAD
for %%F in ("%ZIP%") do echo [OK] Downloaded: %%~zF bytes
echo.

if not exist "%CORE%\" mkdir "%CORE%" >nul 2>nul

echo [2/3] Extracting archive...
if exist "%TMP%" rd /s /q "%TMP%" >nul 2>nul
mkdir "%TMP%" >nul 2>nul

"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "Expand-Archive -Path '%ZIP%' -DestinationPath '%TMP%' -Force"
if errorlevel 1 goto ERR_EXTRACT

if not exist "%TMP%\fzf.exe" goto ERR_NOEXE

echo [3/3] Copying fzf.exe into system_core...
if exist "%CORE%\fzf.exe" del /f /q "%CORE%\fzf.exe" >nul 2>nul
copy /y "%TMP%\fzf.exe" "%CORE%\fzf.exe" >nul
if errorlevel 1 goto ERR_COPY

rd /s /q "%TMP%" >nul 2>nul

echo.
echo [SUCCESS] fzf updated: %CORE%\fzf.exe
goto DONE

:ERR_POWERSHELL
echo [ERROR] PowerShell was not found.
exit /b 1

:ERR_DOWNLOAD
echo [ERROR] Download failed.
exit /b 1

:ERR_EXTRACT
echo [ERROR] Extract failed.
exit /b 1

:ERR_NOEXE
echo [ERROR] fzf.exe was not found after extract.
exit /b 1

:ERR_COPY
echo [ERROR] Copy failed.
exit /b 1

:DONE
if not defined AUDION_NO_PAUSE pause
exit /b 0
