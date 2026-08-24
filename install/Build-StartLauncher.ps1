param(
    [string]$ProjectRoot = "",
    [string]$AppName = "",
    [string]$AppId = "",
    [switch]$RequireAdministrator,
    [switch]$NoIcon
)

$ErrorActionPreference = "Stop"

function Resolve-Root {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    }
    return (Resolve-Path $Value).Path
}

function Get-ToolManifestScalar {
    param(
        [string]$Root,
        [string]$Key
    )
    $manifest = Join-Path $Root "config\tool_manifest.yaml"
    if (-not (Test-Path -LiteralPath $manifest)) {
        return ""
    }
    $inTool = $false
    foreach ($line in Get-Content -LiteralPath $manifest -Encoding UTF8) {
        if ($line -match '^tool:\s*$') {
            $inTool = $true
            continue
        }
        if ($inTool -and $line -match '^\S') {
            break
        }
        if ($inTool -and $line -match ("^\s{2}" + [regex]::Escape($Key) + ":\s*(.+?)\s*$")) {
            $value = $Matches[1].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return ""
}

function Convert-ToAppId {
    param([string]$Name)
    $slug = [regex]::Replace($Name, '[^A-Za-z0-9]+', '.').Trim('.')
    if ([string]::IsNullOrWhiteSpace($slug)) {
        $slug = "Audion.App"
    }
    if ($slug -notmatch '^[A-Za-z]') {
        $slug = "App.$slug"
    }
    if ($slug.StartsWith("Audion.Tools.")) {
        return $slug
    }
    return "Audion.Tools.$slug"
}

function Convert-ToCSharpString {
    param([string]$Value)
    return $Value.Replace("\", "\\").Replace('"', '\"')
}

function Get-StartLauncherPolicyBool {
    param(
        [string]$Root,
        [string]$Key
    )

    $policy = Join-Path $Root "system_core\start_launcher\StartLauncher.policy"
    if (-not (Test-Path -LiteralPath $policy)) {
        return $false
    }

    foreach ($line in Get-Content -LiteralPath $policy -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }
        if ($trimmed -match ("^" + [regex]::Escape($Key) + "\s*=\s*(.+?)\s*$")) {
            $value = $Matches[1].Trim().Trim('"').Trim("'")
            return $value -match '^(1|true|yes|on)$'
        }
    }
    return $false
}

function Resolve-Csc {
    $candidates = @(
        "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "Could not find .NET Framework csc.exe."
}

$root = Resolve-Root $ProjectRoot
if ([string]::IsNullOrWhiteSpace($AppName)) {
    $AppName = Get-ToolManifestScalar -Root $root -Key "name"
}
if ([string]::IsNullOrWhiteSpace($AppName)) {
    $AppName = Split-Path -Leaf $root
}
if ([string]::IsNullOrWhiteSpace($AppId)) {
    $AppId = Convert-ToAppId $AppName
}
$requireAdministratorValue = $RequireAdministrator.IsPresent -or (Get-StartLauncherPolicyBool -Root $root -Key "require_administrator")

$source = Join-Path $root "system_core\start_launcher\StartLauncher.cs"
$manifest = Join-Path $root "system_core\start_launcher\StartLauncher.manifest"
$icon = Join-Path $root "system_core\icons\app.ico"
$output = Join-Path $root "Start.exe"
$buildDir = Join-Path $root "work\build\start_launcher"
$configSource = Join-Path $buildDir "StartLauncherConfig.g.cs"

if (-not (Test-Path -LiteralPath $source)) {
    throw "Start launcher source was not found: $source"
}
if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Start launcher manifest was not found: $manifest"
}

New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

$appNameLiteral = Convert-ToCSharpString $AppName
$appIdLiteral = Convert-ToCSharpString $AppId
$requireAdministratorLiteral = if ($requireAdministratorValue) { "true" } else { "false" }
@"
internal static class StartLauncherConfig
{
    public const string AppName = "$appNameLiteral";
    public const string AppId = "$appIdLiteral";
    public const bool RequireAdministrator = $requireAdministratorLiteral;
}
"@ | Set-Content -LiteralPath $configSource -Encoding UTF8

$csc = Resolve-Csc
$arguments = @(
    "/nologo",
    "/target:winexe",
    "/platform:anycpu",
    "/optimize+",
    "/out:$output",
    "/win32manifest:$manifest",
    "/reference:System.dll",
    "/reference:System.Windows.Forms.dll"
)
if (-not $NoIcon -and (Test-Path -LiteralPath $icon)) {
    $arguments += "/win32icon:$icon"
}
$arguments += @($source, $configSource)

& $csc @arguments
if ($LASTEXITCODE -ne 0) {
    throw "csc.exe failed with exit code $LASTEXITCODE."
}

Write-Host "[OK] Built $output"
Write-Host "[OK] AppName: $AppName"
Write-Host "[OK] AppId: $AppId"
Write-Host "[OK] RequireAdministrator: $requireAdministratorValue"
