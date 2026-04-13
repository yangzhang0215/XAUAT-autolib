param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot "python\.venv\Scripts\python.exe"
$specPath = Join-Path $PSScriptRoot "seminar-gui.spec"
$distPath = Join-Path $projectRoot "dist\xauat-seminar-gui"
$iconPath = Join-Path $projectRoot "assets\xauat-emblem.ico"

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        throw "没有找到 python\.venv\Scripts\python.exe，请先准备好打包环境。"
    }
}

if (-not (Test-Path $PythonExe)) {
    throw "指定的 Python 不存在：$PythonExe"
}

if (-not (Test-Path $iconPath)) {
    throw "没有找到校徽图标：$iconPath"
}

Write-Host "使用解释器：" $PythonExe
Write-Host "开始打包独立研讨室 GUI ..."

& $PythonExe -m PyInstaller --noconfirm --clean $specPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "打包完成。输出目录："
Write-Host $distPath
