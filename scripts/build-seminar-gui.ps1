param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot "python\.venv\Scripts\python.exe"
$specPath = Join-Path $PSScriptRoot "seminar-gui.spec"
$buildPath = Join-Path $projectRoot "build"
$distPath = Join-Path $projectRoot "dist\xauat-seminar-gui"
$iconPath = Join-Path $projectRoot "assets\xauat-emblem.ico"
$configExamplePath = Join-Path $projectRoot "python\seminar.config.example.json"
$portableZipPath = Join-Path $projectRoot "dist\xauat-seminar-gui-portable.zip"

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        throw "Cannot find python\.venv\Scripts\python.exe. Please prepare the packaging environment first."
    }
}

if (-not (Test-Path $PythonExe)) {
    throw "Specified Python does not exist: $PythonExe"
}

if (-not (Test-Path $iconPath)) {
    throw "Cannot find icon file: $iconPath"
}

Write-Host "Using interpreter:" $PythonExe
Write-Host "Building standalone seminar GUI..."

if (Test-Path $distPath) {
    Remove-Item -Recurse -Force $distPath
}

if (Test-Path $buildPath) {
    Remove-Item -Recurse -Force $buildPath
}

if (Test-Path $portableZipPath) {
    Remove-Item -Force $portableZipPath
}

& $PythonExe -m PyInstaller --noconfirm --clean $specPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (Test-Path $configExamplePath) {
    Copy-Item -Force $configExamplePath (Join-Path $distPath "seminar.config.example.json")
}

Compress-Archive -Path $distPath -DestinationPath $portableZipPath

Write-Host ""
Write-Host "Build completed."
Write-Host "Output directory:" $distPath
Write-Host "Portable package:" $portableZipPath
