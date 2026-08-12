$ErrorActionPreference = "Stop"

$UpstreamRepo = "https://github.com/iminashi/Rocksmith2014.NET.git"
$UpstreamCommit = "b87c9a3afd31c40ade9685a9244e718e7581c0cb"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ToolsRoot = Join-Path $RepoRoot ".tools"
$UpstreamPath = Join-Path $ToolsRoot "Rocksmith2014.NET"
$BridgeProject = Join-Path $RepoRoot "tools\psarc_bridge\RocksmithPsarcBridge.fsproj"

function Invoke-GitWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage,
        [int]$Attempts = 3
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        & $Command
        if ($LASTEXITCODE -eq 0) {
            return
        }

        if ($attempt -lt $Attempts) {
            $delaySeconds = 2 * $attempt
            Write-Warning "$FailureMessage Attempt $attempt/$Attempts failed; retrying in $delaySeconds seconds."
            Start-Sleep -Seconds $delaySeconds
        }
    }

    throw "$FailureMessage Failed after $Attempts attempts."
}

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
    Invoke-GitWithRetry -Command {
        git clone --filter=blob:none --no-checkout $UpstreamRepo $UpstreamPath
    } -FailureMessage "Failed to clone Rocksmith2014.NET."
}

Write-Host "Pinning Rocksmith2014.NET to $UpstreamCommit..."
Invoke-GitWithRetry -Command {
    git -C $UpstreamPath fetch origin $UpstreamCommit --depth 1
} -FailureMessage "Failed to fetch pinned Rocksmith2014.NET commit $UpstreamCommit."

git -C $UpstreamPath checkout --detach $UpstreamCommit
if ($LASTEXITCODE -ne 0) { throw "Failed to checkout pinned Rocksmith2014.NET commit $UpstreamCommit." }

Write-Host "Building minimal PSARC/SNG conversion bridge..."
dotnet build $BridgeProject -c Release
if ($LASTEXITCODE -ne 0) {
    throw "PSARC bridge build failed. See dotnet build output above."
}

$BridgeDll = Join-Path $RepoRoot "tools\psarc_bridge\bin\Release\net10.0\RocksmithPsarcBridge.dll"
if (-not (Test-Path $BridgeDll)) {
    throw "Bridge build completed without expected output: $BridgeDll"
}

Write-Host "PSARC bridge ready:"
Write-Host $BridgeDll
Write-Host ""
Write-Host "Use it with:"
Write-Host '  cdlc import-psarc PROJECT --psarc "C:\Path\Song_p.psarc"'
