param(
    [string]$Root,
    [switch]$Apply,
    [switch]$WriteReport
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $installDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $Root = Split-Path -Parent $installDir
}

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$cleanerScriptPath = (Resolve-Path -LiteralPath $MyInvocation.MyCommand.Path).Path
$archiveRoot = Join-Path $rootPath "docs\archive\template_legacy"
$reportPath = Join-Path $rootPath "report\template_legacy_cleanup_report.md"

if (-not (Test-Path -LiteralPath (Join-Path $rootPath "AGENTS.md"))) {
    throw "Project marker not found: AGENTS.md"
}

if (-not (Test-Path -LiteralPath (Join-Path $rootPath "system_core\ui_nicegui\app.py"))) {
    throw "Project marker not found: system_core\ui_nicegui\app.py"
}

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
    "node_modules",
    "output",
    "report",
    "release",
    "runtime",
    "venv",
    "wheelhouse",
    "workspace"
)

$referenceExtensions = @(
    ".cmd",
    ".md",
    ".ps1",
    ".py",
    ".txt",
    ".yaml",
    ".yml"
)

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

function Get-ReferenceFiles {
    $files = New-Object System.Collections.Generic.List[System.IO.FileInfo]
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

            if ($referenceExtensions -contains $item.Extension.ToLowerInvariant()) {
                $files.Add($item)
            }
        }
    }

    @($files | Sort-Object FullName)
}

function Find-References {
    param([Parameter(Mandatory = $true)][string]$CandidatePath)

    $candidateRelative = Get-RelativeDisplayPath -Path $CandidatePath
    $candidateLeaf = Split-Path -Leaf $CandidatePath
    $patterns = @(
        $candidateRelative,
        ($candidateRelative -replace "\\", "/"),
        $candidateLeaf
    ) | Select-Object -Unique

    $hits = New-Object System.Collections.Generic.List[string]
    foreach ($file in Get-ReferenceFiles) {
        if ($file.FullName -ieq $CandidatePath) {
            continue
        }
        if ($file.FullName -ieq $cleanerScriptPath) {
            continue
        }
        if ($file.FullName.StartsWith($archiveRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }

        try {
            $match = Select-String -LiteralPath $file.FullName -SimpleMatch -Pattern $patterns -Quiet -ErrorAction Stop
        } catch {
            $match = $false
        }

        if ($match) {
            $hits.Add((Get-RelativeDisplayPath -Path $file.FullName))
        }
    }

    @($hits | Sort-Object -Unique)
}

function Add-Line {
    param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Items)

    if ($Items.Count -eq 0) {
        $text = ""
    } else {
        $text = [string]$Items[$Items.Count - 1]
    }

    $script:lines.Add($text) | Out-Null
}

function Get-ArchiveDestination {
    param([Parameter(Mandatory = $true)][string]$SourcePath)

    $relative = Get-RelativeDisplayPath -Path $SourcePath
    return Join-Path $archiveRoot $relative
}

function Move-ToArchive {
    param([Parameter(Mandatory = $true)][string]$SourcePath)

    $destination = Get-ArchiveDestination -SourcePath $SourcePath
    $destinationDir = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

    if (Test-Path -LiteralPath $destination) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $destination = "$destination.$stamp"
    }

    Move-Item -LiteralPath $SourcePath -Destination $destination
    return Get-RelativeDisplayPath -Path $destination
}

$archiveCandidates = @()
foreach ($file in Get-ChildItem -LiteralPath $rootPath -Filter "GUI_TEMPLATE_PATCH_NOTES_v*.md" -File -ErrorAction SilentlyContinue) {
    $archiveCandidates += [PSCustomObject]@{
        Path = $file.FullName
        Reason = "Historical patch note already distilled into AGENTS/canon docs."
    }
}

foreach ($relative in @(
    "docs\CODEX_GUI_PORTING_PROMPT_RU.md",
    "docs\GUI_TEMPLATE_POST_ADAPTATION_REFACTOR_PATCH_RU.md",
    "docs\GUI_TEMPLATE_RECOMMENDATIONS_RU.md"
)) {
    $path = Join-Path $rootPath $relative
    if (Test-Path -LiteralPath $path) {
        $archiveCandidates += [PSCustomObject]@{
            Path = $path
            Reason = "Historical helper doc. Keep only if it still adds information beyond UX_UI_CANON/porting guide."
        }
    }
}

$reviewCandidates = @(
    [PSCustomObject]@{
        Path = "CLAUDE.md"
        Reason = "Agent-specific mirror. Keep as a short pointer to AGENTS.md if Claude tooling still reads it."
    },
    [PSCustomObject]@{
        Path = "launcher_project.cmd"
        Reason = "Legacy expert CLI/FZF launcher. Keep if it is a supported debug path. Avoid diverging from builder/GUI behavior."
    },
    [PSCustomObject]@{
        Path = "launcher_project_ru.cmd"
        Reason = "Protected language-specific launcher. RU/EN entry points are allowed. Duplicated behavior must stay synchronized."
    },
    [PSCustomObject]@{
        Path = "launcher_tools.cmd"
        Reason = "Legacy tools launcher. Much of it overlaps builder_main.cmd. Keep only as expert convenience."
    },
    [PSCustomObject]@{
        Path = "install\launcher-tools-update_fzf.cmd"
        Reason = "Optional FZF installer. FZF is compatibility tooling, not required for the GUI path."
    },
    [PSCustomObject]@{
        Path = "system_core\inspect_md_tables.py"
        Reason = "Developer helper, not runtime."
    },
    [PSCustomObject]@{
        Path = "system_core\main.py"
        Reason = "Sample CLI placeholder. Replace in real projects or keep as a harmless smoke target."
    },
    [PSCustomObject]@{
        Path = "GitHub"
        Reason = "Publication copy. Useful for the template repo, usually excluded from project ports."
    }
)

$protectedItems = @(
    [PSCustomObject]@{
        Path = "launcher_gui.cmd"
        Reason = "Main user-facing GUI entry point."
    },
    [PSCustomObject]@{
        Path = "launcher_project_ru.cmd"
        Reason = "Language variant is protected. Only shared behavior drift is a cleanup target."
    },
    [PSCustomObject]@{
        Path = "config"
        Reason = "Source-of-truth project and GUI configuration."
    },
    [PSCustomObject]@{
        Path = "system_core\core"
        Reason = "Reusable runtime core."
    },
    [PSCustomObject]@{
        Path = "system_core\ui_nicegui"
        Reason = "GUI runtime core."
    },
    [PSCustomObject]@{
        Path = "system_core\license"
        Reason = "Release licensing machinery."
    },
    [PSCustomObject]@{
        Path = "tests"
        Reason = "Template safety gates."
    },
    [PSCustomObject]@{
        Path = "docs\UX_UI_CANON_RU.md"
        Reason = "Current UX/UI source of truth."
    },
    [PSCustomObject]@{
        Path = "docs\PROJECT_PORTING_UPGRADE_RU.md"
        Reason = "Current project-upgrade checklist."
    }
)

$generatedPayload = @(
    "input",
    "output",
    "logs",
    "report",
    "workspace",
    "data",
    "release",
    "runtime",
    "wheelhouse",
    "install\download",
    "system_core\powershell",
    "system_core\fzf.exe",
    "install\licenses.zip",
    "._runtime",
    "__pycache__"
)

$lines = New-Object System.Collections.Generic.List[string]
$modeText = if ($Apply) { "APPLY: archive safe candidates only" } else { "DRY-RUN: no files are changed" }

Add-Line "# Template Legacy Cleanup Report"
Add-Line ""
Add-Line ("- Root: {0}" -f $rootPath)
Add-Line "- Mode: $modeText"
Add-Line "- Rule: language variants are protected. Duplicated behavior is a maintenance risk, not a reason to delete localization."
Add-Line ""

Write-Host "======================================================================"
Write-Host "AUDION PYTHON GUI PORTABLE TEMPLATE - LEGACY CLEANER"
Write-Host "======================================================================"
Write-Host "Root: $rootPath"
Write-Host "Mode: $modeText"
Write-Host ""

Add-Line "## Archive Candidates"
Write-Host "[ARCHIVE CANDIDATES]"
$readyCount = 0
$blockedCount = 0
$movedCount = 0

foreach ($candidate in @($archiveCandidates | Sort-Object Path)) {
    if (-not (Test-Path -LiteralPath $candidate.Path)) {
        continue
    }

    $relative = Get-RelativeDisplayPath -Path $candidate.Path
    $references = @(Find-References -CandidatePath $candidate.Path)
    if ($references.Count -gt 0) {
        $blockedCount++
        Write-Host ("  [BLOCKED] {0}" -f $relative)
        Write-Host ("            referenced by: {0}" -f (($references | Select-Object -First 5) -join ", "))
        Add-Line ("- BLOCKED: {0} - {1}" -f $relative, $candidate.Reason)
        Add-Line ("  Referenced by: {0}" -f ($references -join ", "))
        continue
    }

    $readyCount++
    if ($Apply) {
        $destinationRelative = Move-ToArchive -SourcePath $candidate.Path
        $movedCount++
        Write-Host ("  [ARCHIVED] {0} -> {1}" -f $relative, $destinationRelative)
        Add-Line ("- ARCHIVED: {0} -> {1} - {2}" -f $relative, $destinationRelative, $candidate.Reason)
    } else {
        Write-Host ("  [READY] {0}" -f $relative)
        Add-Line ("- READY: {0} - {1}" -f $relative, $candidate.Reason)
    }
}

if ($archiveCandidates.Count -eq 0) {
    Write-Host "  none"
    Add-Line "- None."
}

Add-Line ""
Add-Line "## Manual Review Only"
Write-Host ""
Write-Host "[MANUAL REVIEW ONLY]"
foreach ($candidate in $reviewCandidates) {
    $path = Join-Path $rootPath $candidate.Path
    if (Test-Path -LiteralPath $path) {
        Write-Host ("  [REVIEW] {0} - {1}" -f $candidate.Path, $candidate.Reason)
        Add-Line ("- REVIEW: {0} - {1}" -f $candidate.Path, $candidate.Reason)
    }
}

Add-Line ""
Add-Line "## Protected"
Write-Host ""
Write-Host "[PROTECTED]"
foreach ($item in $protectedItems) {
    $path = Join-Path $rootPath $item.Path
    if (Test-Path -LiteralPath $path) {
        Write-Host ("  [KEEP] {0} - {1}" -f $item.Path, $item.Reason)
        Add-Line ("- KEEP: {0} - {1}" -f $item.Path, $item.Reason)
    }
}

Add-Line ""
Add-Line "## Generated Payload"
Write-Host ""
Write-Host "[GENERATED PAYLOAD]"
foreach ($item in $generatedPayload) {
    Write-Host ("  [cleanup_project.cmd] {0}" -f $item)
    Add-Line ("- {0} is handled by cleanup_project.cmd." -f $item)
}

Add-Line ""
Add-Line "## Summary"
Add-Line ("- Ready archive candidates: {0}" -f $readyCount)
Add-Line ("- Blocked by references: {0}" -f $blockedCount)
Add-Line ("- Archived this run: {0}" -f $movedCount)

Write-Host ""
Write-Host "[SUMMARY]"
Write-Host "  Ready archive candidates: $readyCount"
Write-Host "  Blocked by references:   $blockedCount"
Write-Host "  Archived this run:       $movedCount"

if ($WriteReport) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
    [System.IO.File]::WriteAllLines($reportPath, $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Host ""
    Write-Host "[REPORT] $(Get-RelativeDisplayPath -Path $reportPath)"
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry-run only. To archive unreferenced candidates:"
    Write-Host "  install\cleanup_template_legacy.cmd -Apply -WriteReport"
}
