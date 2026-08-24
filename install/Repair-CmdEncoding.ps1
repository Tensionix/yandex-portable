param(
    [string]$Root,
    [switch]$Fix,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $installDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $Root = Split-Path -Parent $installDir
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$excludedDirectoryNames = @(
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv_latest",
    "._runtime",
    "__pycache__",
    "data",
    "input",
    "logs",
    "models",
    "node_modules",
    "output",
    "powershell",
    "report",
    "release",
    "runtime",
    "Tools",
    "venv",
    "wheelhouse",
    "workspace"
)

$utf8Strict = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false, $true
$utf8NoBom = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false

function Get-RelativeDisplayPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if ($fullPath.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $fullPath.Substring($rootPath.Length).TrimStart("\", "/")
    }
    return $fullPath
}

function Test-ExcludedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $relative = Get-RelativeDisplayPath -Path $Path
    foreach ($part in ($relative -split "[\\/]")) {
        if ($excludedDirectoryNames -contains $part) {
            return $true
        }
    }
    return $false
}

function Get-CmdEncodingState {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    $finalNewline = $bytes.Length -eq 0 -or $bytes[$bytes.Length - 1] -eq 0x0A -or $bytes[$bytes.Length - 1] -eq 0x0D
    $crlf = 0
    $loneLf = 0
    $loneCr = 0

    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($bytes[$i] -eq 0x0A) {
            if ($i -gt 0 -and $bytes[$i - 1] -eq 0x0D) {
                $crlf++
            } else {
                $loneLf++
            }
        } elseif ($bytes[$i] -eq 0x0D -and ($i + 1 -ge $bytes.Length -or $bytes[$i + 1] -ne 0x0A)) {
            $loneCr++
        }
    }

    $offset = 0
    if ($hasBom) {
        $offset = 3
    }

    $validUtf8 = $true
    $errorText = ""
    try {
        [void]$utf8Strict.GetString($bytes, $offset, $bytes.Length - $offset)
    } catch {
        $validUtf8 = $false
        $errorText = $_.Exception.Message
    }

    [PSCustomObject]@{
        Path = $Path
        RelativePath = Get-RelativeDisplayPath -Path $Path
        HasBom = $hasBom
        Crlf = $crlf
        LoneLf = $loneLf
        LoneCr = $loneCr
        ValidUtf8 = $validUtf8
        FinalNewline = $finalNewline
        ErrorText = $errorText
        Ok = (-not $hasBom -and $loneLf -eq 0 -and $loneCr -eq 0 -and $validUtf8 -and $finalNewline)
    }
}

function Repair-CmdEncoding {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $offset = 0
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $offset = 3
    }

    $text = $utf8Strict.GetString($bytes, $offset, $bytes.Length - $offset)
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }

    $text = $text -replace "`r`n", "`n"
    $text = $text -replace "`r", "`n"
    $text = $text -replace "`n", "`r`n"
    if ($text.Length -gt 0 -and -not $text.EndsWith("`r`n")) {
        $text += "`r`n"
    }

    [System.IO.File]::WriteAllText($Path, $text, $utf8NoBom)
}

$cmdFiles = New-Object System.Collections.Generic.List[System.IO.FileInfo]
$pendingDirs = New-Object System.Collections.Generic.Stack[string]
$pendingDirs.Push($rootPath)

while ($pendingDirs.Count -gt 0) {
    $currentDir = $pendingDirs.Pop()
    foreach ($item in Get-ChildItem -LiteralPath $currentDir -Force -ErrorAction Stop) {
        if ($item.PSIsContainer) {
            if (-not (Test-ExcludedPath -Path $item.FullName)) {
                $pendingDirs.Push($item.FullName)
            }
            continue
        }

        if ($item.Extension -ieq ".cmd" -and -not (Test-ExcludedPath -Path $item.FullName)) {
            $cmdFiles.Add($item)
        }
    }
}

$cmdFiles = @($cmdFiles | Sort-Object FullName)

$badStates = New-Object System.Collections.Generic.List[object]
$fixedStates = New-Object System.Collections.Generic.List[object]

foreach ($file in $cmdFiles) {
    $state = Get-CmdEncodingState -Path $file.FullName
    if ($state.Ok) {
        continue
    }

    if ($Fix -and $state.ValidUtf8) {
        Repair-CmdEncoding -Path $file.FullName
        $state = Get-CmdEncodingState -Path $file.FullName
        $fixedStates.Add($state)
        if ($state.Ok) {
            continue
        }
    }

    $badStates.Add($state)
}

if (-not $Quiet) {
    foreach ($state in $fixedStates) {
        Write-Host ("[FIXED] {0} BOM={1} CRLF={2} LoneLF={3} LoneCR={4} UTF8={5} FinalNL={6}" -f $state.RelativePath, $state.HasBom, $state.Crlf, $state.LoneLf, $state.LoneCr, $state.ValidUtf8, $state.FinalNewline)
    }
}

if ($badStates.Count -gt 0) {
    Write-Host "[ERROR] CMD encoding check failed."
    foreach ($state in $badStates) {
        Write-Host ("  - {0} BOM={1} CRLF={2} LoneLF={3} LoneCR={4} UTF8={5} FinalNL={6} {7}" -f $state.RelativePath, $state.HasBom, $state.Crlf, $state.LoneLf, $state.LoneCr, $state.ValidUtf8, $state.FinalNewline, $state.ErrorText)
    }
    exit 1
}

if (-not $Quiet) {
    Write-Host ("[OK] CMD encoding: {0} file(s) checked." -f $cmdFiles.Count)
}
