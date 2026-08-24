$ErrorActionPreference = "Stop"

$installDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $installDir
$downloadDir = Join-Path $installDir "download"
$runtimeDir = Join-Path $rootDir "runtime"
$wheelhouseDir = Join-Path $rootDir "wheelhouse"
$requirementsFile = Join-Path $installDir "requirements_full.in"
$doctorScript = Join-Path $rootDir "system_core\doctor.py"
$guiSmokeScript = Join-Path $rootDir "system_core\ui_nicegui\app.py"

$pythonMinor = 12
$headers = @{ 'User-Agent' = 'Audion-Python-Portable-Template' }

$pyPatch = -1
for ($i = 0; $i -le 40; $i++) {
    $uri = "https://www.python.org/ftp/python/3.$pythonMinor.$i/python-3.$pythonMinor.$i-embed-amd64.zip"
    try {
        Invoke-WebRequest -Headers $headers -Uri $uri -Method Head -TimeoutSec 10 | Out-Null
        $pyPatch = $i
    } catch {
        if ($pyPatch -ge 0) { break }
    }
}
if ($pyPatch -lt 0) { throw "Could not resolve any Python 3.$pythonMinor.x embed-amd64 build" }
$pythonVersion = "3.$pythonMinor.$pyPatch"
$pythonZipName = "python-$pythonVersion-embed-amd64.zip"
$pythonUrl = "https://www.python.org/ftp/python/$pythonVersion/$pythonZipName"
$pythonZipPath = Join-Path $downloadDir $pythonZipName
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$getPipPath = Join-Path $downloadDir "get-pip.py"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Write-Host "======================================================================"
Write-Host "AUDION PYTHON PORTABLE TEMPLATE - BUILD PORTABLE ENV (PS)"
Write-Host "======================================================================"
Write-Host "Root:        $rootDir"
Write-Host "Install:     $installDir"
Write-Host "Download:    $downloadDir"
Write-Host "Runtime:     $runtimeDir"
Write-Host "Wheelhouse:  $wheelhouseDir"
Write-Host ""

New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $wheelhouseDir | Out-Null

Write-Host "[1/6] Downloading Python Embedded..."
Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZipPath

Write-Host "[2/6] Extracting runtime..."
if (Test-Path $runtimeDir) {
    Get-ChildItem -Force $runtimeDir | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
}
Expand-Archive -Path $pythonZipPath -DestinationPath $runtimeDir -Force

Write-Host "[3/6] Enabling import site..."
$pthFile = Join-Path $runtimeDir "python3$pythonMinor._pth"
if (-not (Test-Path $pthFile)) {
    throw "Missing file: $pthFile"
}
(Get-Content $pthFile) -replace '^#import site$', 'import site' | Set-Content $pthFile -Encoding ASCII

Write-Host "[4/6] Downloading get-pip.py..."
# A dropped connection here used to kill the whole project build.
$getPipOk = $false
foreach ($getPipTry in 1..5) {
    $getPipTmp = "$($getPipPath).part"
    try {
        Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipTmp -TimeoutSec 120 -UseBasicParsing
        $getPipSize = (Get-Item -LiteralPath $getPipTmp).Length
        if ($getPipSize -lt 1000000) { throw "truncated body: $getPipSize bytes" }
        Move-Item -LiteralPath $getPipTmp -Destination $getPipPath -Force
        $getPipOk = $true
        break
    } catch {
        Write-Host "  get-pip.py attempt $getPipTry failed: $($_.Exception.Message)"
        Remove-Item -LiteralPath $getPipTmp -Force -ErrorAction SilentlyContinue
        if ($getPipTry -lt 5) { Start-Sleep -Seconds (3 * $getPipTry) }
    }
}
if (-not $getPipOk) { throw "Could not download get-pip.py after 5 attempts - the network dropped every time." }
$pythonExe = Join-Path $runtimeDir "python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Missing file: $pythonExe"
}

Write-Host "[5/6] Installing pip..."
Invoke-Checked -Label "Installing pip" -Command { & $pythonExe $getPipPath }

Write-Host "[6/6] Building wheelhouse and installing packages..."
Get-ChildItem -Force $wheelhouseDir |
    Where-Object { $_.Name -ne ".gitkeep" } |
    Remove-Item -Force -Recurse
Invoke-Checked -Label "Installing build bootstrap" -Command {
    & $pythonExe -m pip install --disable-pip-version-check --upgrade setuptools wheel packaging
}
Invoke-Checked -Label "Building wheelhouse" -Command {
    & $pythonExe -m pip wheel --disable-pip-version-check --prefer-binary --no-build-isolation --timeout 120 --retries 12 -r $requirementsFile -w $wheelhouseDir
}
Invoke-Checked -Label "Installing packages" -Command {
    & $pythonExe -m pip install --disable-pip-version-check --no-build-isolation --no-index --find-links=$wheelhouseDir -r $requirementsFile
}

Write-Host "[verify] Verifying environment..."
Invoke-Checked -Label "Verifying environment" -Command { & $pythonExe $doctorScript --project-root $rootDir }
if (Test-Path $guiSmokeScript) {
    Invoke-Checked -Label "Verifying NiceGUI smoke" -Command { & $pythonExe $guiSmokeScript --smoke }
}

Write-Host ""
Write-Host "[SUCCESS] Portable environment is ready."
Write-Host "[INFO] Release licensing is generated later from the finalized release contents."
