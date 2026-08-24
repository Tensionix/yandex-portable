<#
.SYNOPSIS
  Audion - clean reproducible install cache.

.DESCRIPTION
  Removes transient installer/download artifacts while preserving portable
  payloads needed by fresh offline repair/rebuild.

  Removed when present:
    - cached files/folders inside install\download\, except the preserve list
      below;
    - exact installer staging directories system_core\_pwsh_tmp and
      system_core\_fzf_tmp;
    - Python __pycache__ directories and *.pyc/*.pyo files outside payload and
      user-data zones.

  Preserved:
    - .gitkeep
    - get-pip.py
    - 7z*-extra.7z

  The script does not touch runtime\, wheelhouse\, system_core\powershell\,
  system_core\fzf.exe, input/output/logs/report/data/release/workspace, user
  config, or project business data.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [switch]$SkipBytecode
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd('\')
$downloadDir = Join-Path $root 'install\download'

function Join-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    [System.IO.Path]::GetFullPath((Join-Path $root $RelativePath))
}

function Test-IsInsideRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    return $full.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or
        $full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-IsUnderAny {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$Roots
    )
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    foreach ($candidateRoot in $Roots) {
        $candidate = [System.IO.Path]::GetFullPath($candidateRoot).TrimEnd('\')
        if ($full.Equals($candidate, [System.StringComparison]::OrdinalIgnoreCase) -or
            $full.StartsWith($candidate + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-ItemBytes {
    param([Parameter(Mandatory = $true)]$Item)
    if ($Item.PSIsContainer) {
        $sum = (Get-ChildItem -LiteralPath $Item.FullName -File -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
        if ($null -eq $sum) { return 0 }
        return [int64]$sum
    }
    return [int64]$Item.Length
}

function Add-Candidate {
    param(
        [Parameter(Mandatory = $true)]$Item,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    if (-not (Test-IsInsideRoot -Path $Item.FullName)) {
        throw "Refusing to remove outside project root: $($Item.FullName)"
    }

    $bytes = Get-ItemBytes -Item $Item
    $record = [pscustomobject]@{
        Item   = $Item
        Path   = $Item.FullName
        Name   = $Item.Name
        Bytes  = $bytes
        Reason = $Reason
    }
    $script:candidates += $record
}

function Remove-Candidate {
    param([Parameter(Mandatory = $true)]$Candidate)
    $item = $Candidate.Item
    if ($PSCmdlet.ShouldProcess($Candidate.Path, $Candidate.Reason)) {
        if ($item.PSIsContainer) {
            Remove-Item -LiteralPath $Candidate.Path -Recurse -Force -ErrorAction Stop
        }
        else {
            Remove-Item -LiteralPath $Candidate.Path -Force -ErrorAction Stop
        }
        $script:removed += $Candidate
    }
}

function Get-BytecodeCandidates {
    param([Parameter(Mandatory = $true)][string[]]$ExcludedRoots)

    $stack = [System.Collections.Generic.Stack[string]]::new()
    $stack.Push($root)

    while ($stack.Count -gt 0) {
        $dir = $stack.Pop()
        if (Test-IsUnderAny -Path $dir -Roots $ExcludedRoots) {
            continue
        }

        foreach ($child in Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue) {
            if ($child.PSIsContainer) {
                if ($child.Name -in @('.git', '.venv', 'venv', 'node_modules')) {
                    continue
                }
                if ($child.FullName -ne $root -and $child.Name -eq 'Audion Yandex Portable') {
                    continue
                }
                if (Test-IsUnderAny -Path $child.FullName -Roots $ExcludedRoots) {
                    continue
                }
                if ($child.Name -eq '__pycache__') {
                    $child
                    continue
                }
                $stack.Push($child.FullName)
            }
            elseif ($child.Extension -in @('.pyc', '.pyo')) {
                $child
            }
        }
    }
}

$preserveNames = @('.gitkeep', 'get-pip.py')
$preservePatterns = @('7z*-extra.7z')
$script:candidates = @()
$script:removed = @()
$kept = @()

Write-Host '======================================================================'
Write-Host '  AUDION - CLEAN INSTALL CACHE'
Write-Host '======================================================================'
Write-Host "Project: $root"
Write-Host 'Targets: install\download\, installer staging dirs, Python bytecode caches'
Write-Host ''

if (Test-Path -LiteralPath $downloadDir) {
    foreach ($item in Get-ChildItem -LiteralPath $downloadDir -Force -ErrorAction SilentlyContinue) {
        $isPreserved = (-not $item.PSIsContainer) -and ($preserveNames -contains $item.Name)
        if (-not $isPreserved -and -not $item.PSIsContainer) {
            foreach ($pattern in $preservePatterns) {
                if ($item.Name -like $pattern) {
                    $isPreserved = $true
                    break
                }
            }
        }

        if ($isPreserved) {
            $kept += $item
            continue
        }

        Add-Candidate -Item $item -Reason 'Remove cached install artifact'
    }
}
else {
    Write-Host "[skip] $downloadDir does not exist."
}

$stagingDirs = @(
    (Join-ProjectPath 'system_core\_pwsh_tmp'),
    (Join-ProjectPath 'system_core\_fzf_tmp')
)
foreach ($stagingDir in $stagingDirs) {
    if (Test-Path -LiteralPath $stagingDir) {
        $item = Get-Item -LiteralPath $stagingDir -Force
        Add-Candidate -Item $item -Reason 'Remove installer staging directory'
    }
}

if (-not $SkipBytecode) {
    $excludedBytecodeRoots = @(
        (Join-ProjectPath 'runtime'),
        (Join-ProjectPath 'wheelhouse'),
        (Join-ProjectPath 'system_core\powershell'),
        (Join-ProjectPath 'input'),
        (Join-ProjectPath 'output'),
        (Join-ProjectPath 'logs'),
        (Join-ProjectPath 'report'),
        (Join-ProjectPath 'data'),
        (Join-ProjectPath 'release'),
        (Join-ProjectPath 'workspace')
    )
    foreach ($bytecodeItem in Get-BytecodeCandidates -ExcludedRoots $excludedBytecodeRoots) {
        Add-Candidate -Item $bytecodeItem -Reason 'Remove Python bytecode cache'
    }
}

$candidateBytes = ($script:candidates | Measure-Object -Property Bytes -Sum).Sum
if ($null -eq $candidateBytes) { $candidateBytes = 0 }
Write-Host ('Found removable: {0} item(s), {1:N1} MB total.' -f $script:candidates.Count, ($candidateBytes / 1MB))
Write-Host ''

foreach ($candidate in $script:candidates) {
    Remove-Candidate -Candidate $candidate
}

Write-Host '----------------------------------------------------------------------'
$removedBytes = ($script:removed | Measure-Object -Property Bytes -Sum).Sum
if ($null -eq $removedBytes) { $removedBytes = 0 }
Write-Host ('Removed: {0} item(s), {1:N1} MB freed.' -f $script:removed.Count, ($removedBytes / 1MB))
foreach ($entry in $script:removed) {
    Write-Host ('  - {0,-60} {1,8:N1} MB' -f $entry.Name, ($entry.Bytes / 1MB))
}

if ($kept.Count -gt 0) {
    Write-Host ''
    Write-Host ('Kept: {0} file(s) from preserve list.' -f $kept.Count)
    foreach ($file in $kept) {
        Write-Host ('  - {0,-60} {1,8:N1} MB' -f $file.Name, ($file.Length / 1MB))
    }
}

Write-Host ''
exit 0
