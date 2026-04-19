param()

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $projectRoot "dist"
$packageRoot = Join-Path $distRoot "xauat-seminar-cli-mac"
$zipPath = Join-Path $distRoot "xauat-seminar-cli-mac.zip"

$readmePath = Join-Path $packageRoot "README.txt"
$requirementsPath = Join-Path $packageRoot "requirements.txt"
$runnerPath = Join-Path $packageRoot "run.sh"
$pythonPackageRoot = Join-Path $packageRoot "python"
$sourcePythonRoot = Join-Path $projectRoot "python"

$readmeText = @'
XAUAT seminar CLI for macOS

Contents
- run.sh
- requirements.txt
- python/seminar_cli.py
- python/seminar.config.example.json
- python/libspace_cli/

Quick start
1. Open Terminal and enter this folder.
2. Install dependencies:
   bash run.sh install
3. Copy the config template:
   cp python/seminar.config.example.json python/seminar.config.local.json
4. Edit the config:
   nano python/seminar.config.local.json

Useful commands
- bash run.sh doctor
- bash run.sh discover
- bash run.sh reserve-now
- bash run.sh reserve-wait
- bash run.sh reserve --force --room-id 51

Output files
- python/runtime/logs/
- python/runtime/state.json
- python/runtime/seminar-tool-discover-YYYYMMDD.json
- python/runtime/seminar-tool-discover-YYYYMMDD.txt
'@

$requirementsText = @'
requests>=2.32.0,<3.0.0
pycryptodome>=3.20.0,<4.0.0
'@

$runnerText = @'
#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ -f "$SCRIPT_DIR/python/seminar_cli.py" ]]; then
  PROJECT_DIR="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../python/seminar_cli.py" ]]; then
  PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  echo "Cannot locate python/seminar_cli.py from $SCRIPT_DIR" >&2
  exit 1
fi

REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
VENV_DIR="$PROJECT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

usage() {
  cat <<'EOF'
Usage:
  bash run.sh install
  bash run.sh doctor
  bash run.sh discover [extra args]
  bash run.sh reserve-now [extra args]
  bash run.sh reserve-wait [extra args]
  bash run.sh reserve [extra args]

Examples:
  bash run.sh install
  bash run.sh doctor
  bash run.sh discover
  bash run.sh reserve-now
  bash run.sh reserve --force --room-id 51
EOF
}

ensure_system_python() {
  if ! command -v "$SYSTEM_PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python interpreter not found: $SYSTEM_PYTHON_BIN" >&2
    exit 1
  fi
}

ensure_runtime_python() {
  if [[ -x "$VENV_PYTHON" ]]; then
    printf '%s\n' "$VENV_PYTHON"
    return 0
  fi

  ensure_system_python
  printf '%s\n' "$SYSTEM_PYTHON_BIN"
}

install_deps() {
  ensure_system_python
  if [[ ! -x "$VENV_PYTHON" ]]; then
    "$SYSTEM_PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"
}

cd "$PROJECT_DIR"

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
  usage
  exit 1
fi
shift || true

RUNTIME_PYTHON="$(ensure_runtime_python)"

case "$COMMAND" in
  install)
    install_deps
    exec "$VENV_PYTHON" -c "from Crypto.Cipher import AES; import requests; print('Dependency check passed.')"
    ;;
  doctor)
    exec "$RUNTIME_PYTHON" -c "import sys; print(sys.executable); from Crypto.Cipher import AES; import requests; print('Dependency check passed.')"
    ;;
  discover)
    exec "$RUNTIME_PYTHON" python/seminar_cli.py discover "$@"
    ;;
  reserve-now)
    exec "$RUNTIME_PYTHON" python/seminar_cli.py reserve --force "$@"
    ;;
  reserve-wait)
    exec "$RUNTIME_PYTHON" python/seminar_cli.py reserve --wait "$@"
    ;;
  reserve)
    exec "$RUNTIME_PYTHON" python/seminar_cli.py reserve "$@"
    ;;
  *)
    usage
    exit 1
    ;;
esac
'@

if (Test-Path $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $pythonPackageRoot -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $sourcePythonRoot "seminar_cli.py") -Destination (Join-Path $pythonPackageRoot "seminar_cli.py")
Copy-Item -LiteralPath (Join-Path $sourcePythonRoot "seminar.config.example.json") -Destination (Join-Path $pythonPackageRoot "seminar.config.example.json")
Copy-Item -LiteralPath (Join-Path $sourcePythonRoot "libspace_cli") -Destination (Join-Path $pythonPackageRoot "libspace_cli") -Recurse
Get-ChildItem -LiteralPath $packageRoot -Recurse -Directory -Force | Where-Object { $_.Name -eq "__pycache__" } | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $packageRoot -Recurse -File -Force | Where-Object { $_.Extension -in ".pyc", ".pyo" } | Remove-Item -Force

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($readmePath, $readmeText, $utf8NoBom)
[System.IO.File]::WriteAllText($requirementsPath, $requirementsText, $utf8NoBom)
[System.IO.File]::WriteAllText($runnerPath, $runnerText, $utf8NoBom)

Compress-Archive -Path $packageRoot -DestinationPath $zipPath

Write-Host "Packaged Mac CLI:"
Write-Host $packageRoot
Write-Host $zipPath
