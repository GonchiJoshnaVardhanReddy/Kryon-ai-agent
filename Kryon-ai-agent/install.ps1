# Kryon install script — Windows PowerShell
# Full implementation lands in File #15. This is a placeholder that verifies Python.

$ErrorActionPreference = "Stop"

Write-Host "🐙 Kryon install (placeholder — full installer lands in File #15)" -ForegroundColor Cyan

# Verify Python 3.12+
$pyVersion = & py -3.12 --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python 3.12+ is required (use the 'py' launcher)" -ForegroundColor Red
    Write-Host "   Install from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}
Write-Host "Found: $pyVersion" -ForegroundColor Green

# Create venv
py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1

# Install
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Write-Host "✅ Kryon installed. Try: kryon --version" -ForegroundColor Green
