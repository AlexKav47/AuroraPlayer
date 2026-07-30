$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

$compilerCandidates = @(
    $env:INNO_ISCC,
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe")
)
$compiler = $compilerCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1

if (-not $compiler) {
    throw "Install Inno Setup 7 from https://jrsoftware.org/isdl.php, then run this script again."
}

$portableExecutable = Join-Path $projectRoot "release\AuroraPlayer\AuroraPlayer.exe"
if (-not (Test-Path -LiteralPath $portableExecutable)) {
    throw "Build the portable AuroraPlayer folder first by running build.ps1."
}

& $compiler (Join-Path $projectRoot "installer\AuroraPlayer.iss")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Windows setup application built:"
Write-Host "release\AuroraPlayer-v1.1.0-Setup.exe"
