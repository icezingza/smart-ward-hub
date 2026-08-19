[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$RuntimeRoot = if ($env:SMART_WARD_RUNTIME_ROOT) { $env:SMART_WARD_RUNTIME_ROOT } else { Join-Path $ProjectRoot "runtime" }
$LogRoot = if ($env:SMART_WARD_LOG_ROOT) { $env:SMART_WARD_LOG_ROOT } else { Join-Path $RuntimeRoot "logs" }
$Python = if ($env:SMART_WARD_PYTHON) { $env:SMART_WARD_PYTHON } else { Join-Path $ProjectRoot ".venv\Scripts\python.exe" }

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null

$env:SW_ENVIRONMENT = "pilot"
$env:SW_AUTO_CREATE_DB = "false"
$env:SW_SEED_DATA = "false"
$env:SW_ENABLE_DOCS = "false"
$env:SW_ALLOWED_HOSTS = "127.0.0.1,localhost"
$env:SW_ALLOWED_ORIGINS = ""
$env:SW_AUTH_MODE = if ($env:SW_AUTH_MODE) { $env:SW_AUTH_MODE } else { "oidc" }
$env:SW_DATABASE_PATH = Join-Path $RuntimeRoot "ward_hub.db"
$env:SW_TELEMETRY_STATE_PATH = Join-Path $RuntimeRoot "edge_telemetry_state.json"
$env:SW_AUDIT_LOG_PATH = Join-Path $LogRoot "audit_events.jsonl"
$env:SW_FORENSIC_ANCHOR_PATH = Join-Path $RuntimeRoot "forensic_anchors.jsonl"
$env:SW_SQLITE_SYNCHRONOUS = "FULL"
$env:SW_DEVICE_TRUST_MODE = if ($env:SW_DEVICE_TRUST_MODE) { $env:SW_DEVICE_TRUST_MODE } else { "observe" }

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python environment not found: $Python. Create .venv and install requirements before auto-run."
}

$readinessArgs = @("deployment_readiness.py", "--host", "127.0.0.1", "--port", "$Port", "--project-root", $ProjectRoot)
& $Python @readinessArgs
if ($LASTEXITCODE -ne 0) {
    throw "Deployment readiness failed closed. No Edge service was started."
}

if ($ValidateOnly) {
    Write-Output "SMART_WARD_HUB_WINDOWS_READINESS_PASSED"
    exit 0
}

Set-Location -LiteralPath $ProjectRoot
& $Python -m uvicorn main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
