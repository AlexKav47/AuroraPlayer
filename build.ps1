$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$vlcCandidates = @(
    (Join-Path $env:ProgramFiles "VideoLAN\VLC"),
    (Join-Path ${env:ProgramFiles(x86)} "VideoLAN\VLC")
)
$vlcSource = $vlcCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $_ "libvlc.dll")) } |
    Select-Object -First 1

if (-not $vlcSource) {
    throw "The build computer needs VLC so its redistributable engine can be embedded. Target computers will not need VLC."
}

$buildPython = $env:AURORA_BUILD_PYTHON
if ($buildPython) {
    if (-not (Test-Path -LiteralPath $buildPython)) {
        throw "AURORA_BUILD_PYTHON does not point to a Python executable: $buildPython"
    }
} else {
    if (-not (Test-Path -LiteralPath ".venv")) {
        python -m venv .venv
    }
    $buildPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
}

& $buildPython -c "import PySide6, vlc, PyInstaller"
if ($LASTEXITCODE -ne 0) {
    & $buildPython -m pip install -r requirements.txt pyinstaller
}

$pyinstallerArguments = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--contents-directory", "runtime",
    "--windowed",
    "--noupx",
    "--name", "AuroraPlayer",
    "--icon", (Join-Path $projectRoot "aurora_player\assets\aurora-player.ico"),
    "--distpath", (Join-Path $projectRoot "release"),
    "--workpath", (Join-Path $projectRoot "build\pyinstaller"),
    "--specpath", (Join-Path $projectRoot "build"),
    "--paths", $projectRoot,
    "--add-data", ((Join-Path $projectRoot "aurora_player\skins") + ";aurora_player\skins"),
    "--add-data", ((Join-Path $projectRoot "aurora_player\extensions") + ";aurora_player\extensions"),
    "--add-data", ((Join-Path $projectRoot "aurora_player\assets") + ";aurora_player\assets"),
    "--add-data", ((Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") + ";."),
    "--add-binary", "$vlcSource\libvlc.dll;vlc",
    "--add-binary", "$vlcSource\libvlccore.dll;vlc",
    "--add-binary", "$vlcSource\vlc.exe;vlc",
    "--add-data", "$vlcSource\plugins;vlc\plugins",
    "--add-data", "$vlcSource\lua;vlc\lua",
    "--add-data", "$vlcSource\hrtfs;vlc\hrtfs",
    "--add-data", "$vlcSource\COPYING.txt;vlc",
    "--add-data", "$vlcSource\AUTHORS.txt;vlc",
    "--add-data", "$vlcSource\README.txt;vlc",
    (Join-Path $projectRoot "launcher.py")
)

& $buildPython -m PyInstaller @pyinstallerArguments

$portableFolder = Join-Path $projectRoot "release\AuroraPlayer"
$portableZip = Join-Path $projectRoot "release\AuroraPlayer-v1.4.0-Portable.zip"
$runtimeFolder = Join-Path $portableFolder "runtime"

# Aurora uses its own Qt interface and English labels, so GUI front ends,
# translations, virtual-keyboard/QML components, PDF support, and alternate
# headless Qt platforms are unnecessary. Removing them keeps the portable
# release materially smaller without removing codecs, disc support, filters,
# subtitles, streaming, or conversion modules.
$pruneTargets = @(
    (Join-Path $runtimeFolder "vlc\plugins\gui"),
    (Join-Path $runtimeFolder "PySide6\translations"),
    (Join-Path $runtimeFolder "PySide6\plugins\generic"),
    (Join-Path $runtimeFolder "PySide6\plugins\platforminputcontexts"),
    (Join-Path $runtimeFolder "PySide6\plugins\imageformats\qpdf.dll"),
    (Join-Path $runtimeFolder "PySide6\plugins\platforms\qdirect2d.dll"),
    (Join-Path $runtimeFolder "PySide6\plugins\platforms\qminimal.dll"),
    (Join-Path $runtimeFolder "PySide6\plugins\platforms\qoffscreen.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6Pdf.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6Quick.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6Qml.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6QmlMeta.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6QmlModels.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6QmlWorkerScript.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6VirtualKeyboard.dll"),
    (Join-Path $runtimeFolder "PySide6\Qt6OpenGL.dll"),
    (Join-Path $runtimeFolder "PySide6\opengl32sw.dll")
)
foreach ($target in $pruneTargets) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

Copy-Item -LiteralPath (Join-Path $projectRoot "release\README.txt") -Destination (Join-Path $portableFolder "README.txt") -Force
Compress-Archive -Path (Join-Path $portableFolder "*") -DestinationPath $portableZip -CompressionLevel Optimal -Force

Write-Host ""
Write-Host "Fast portable application built:"
Write-Host "release\AuroraPlayer\AuroraPlayer.exe"
Write-Host "release\AuroraPlayer-v1.4.0-Portable.zip"
Write-Host ""
Write-Host "Extract the ZIP once, then double-click AuroraPlayer.exe."
Write-Host "The target computer does not need Python or VLC."
