$ErrorActionPreference = "Stop"

$UpstreamRepo = "https://github.com/iminashi/Rocksmith2014.NET.git"
$UpstreamCommit = "b87c9a3afd31c40ade9685a9244e718e7581c0cb"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ToolsRoot = Join-Path $RepoRoot ".tools"
$UpstreamPath = Join-Path $ToolsRoot "Rocksmith2014.NET"
$BridgeProject = Join-Path $RepoRoot "tools\psarc_bridge\RocksmithPsarcBridge.fsproj"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required to bootstrap the PSARC bridge."
}
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw ".NET 10 SDK is required to build the PSARC bridge. Install it, then rerun this script."
}

$dotnetVersion = (& dotnet --version).Trim()
$major = [int]($dotnetVersion.Split('.')[0])
if ($major -lt 10) {
    throw ".NET 10 SDK is required; found $dotnetVersion."
}

New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null

if (-not (Test-Path (Join-Path $UpstreamPath ".git"))) {
    Write-Host "Cloning Rocksmith2014.NET into the gitignored tools cache..."
    git clone --filter=blob:none --no-checkout $UpstreamRepo $UpstreamPath
}

Write-Host "Pinning Rocksmith2014.NET to $UpstreamCommit..."
git -C $UpstreamPath fetch origin $UpstreamCommit --depth 1
git -C $UpstreamPath checkout --detach $UpstreamCommit

Write-Host "Building PSARC bridge..."
dotnet build $BridgeProject -c Release

$BridgeDll = Join-Path $RepoRoot "tools\psarc_bridge\bin\Release\net10.0\RocksmithPsarcBridge.dll"
if (-not (Test-Path $BridgeDll)) {
    throw "Bridge build completed without expected output: $BridgeDll"
}

Write-Host "PSARC bridge ready:"
Write-Host $BridgeDll
Write-Host ""
Write-Host "Use it with:"
Write-Host '  cdlc import-psarc PROJECT --psarc "C:\Path\Song_p.psarc"'
