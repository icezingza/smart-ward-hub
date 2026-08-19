# Windows Acer Fixed Hub Deployment Template

This directory contains a **deployment template**, not an executed Acer installation. It is designed for the Acer Spin N17H2 Fixed Hub candidate and starts the Edge service on loopback after validating pilot configuration. It does not create accounts, configure Windows Firewall, install certificates, register Task Scheduler or modify the user's computer automatically.

## Preconditions

The operator must install Python 3.12 or a compatible tested runtime, create `.venv`, install `requirements.txt`, place the project in an approved directory, create a protected runtime directory outside the source tree and provide OIDC/mTLS secrets through an approved Windows secret mechanism. Static bearer tokens are acceptable only for local bench or development use.

The runtime directory should be ACL-restricted to the service account. The database, telemetry checkpoint, audit log and local forensic anchor should not live inside the Git checkout. The project must be kept on an encrypted volume when required by the hospital host policy.

## Readiness-only command

From PowerShell:

```powershell
.\deploy\windows\start_smart_ward_hub.ps1 -ValidateOnly
```

The validator requires pilot-safe defaults: `SW_ENVIRONMENT=pilot`, no automatic database creation, no seed data, disabled API docs, explicit non-wildcard hosts, loopback binding, runtime paths outside the source tree and a valid OIDC-shaped configuration when `SW_AUTH_MODE=oidc`.

## Manual start command

```powershell
.\deploy\windows\start_smart_ward_hub.ps1
```

The service binds to `127.0.0.1` only. It does not expose the Hub directly to the ward network. A separate authenticated and reviewed gateway is required before any remote access is allowed.

## Auto-run adaptation

For an appliance-like boot experience, the hospital host operator may register the `.cmd` wrapper with Windows Task Scheduler under a dedicated least-privilege account, configured to run only after the approved runtime directory, secret source and network/time prerequisites are available. The task must capture stdout/stderr to an access-controlled log location, restart on failure according to the approved policy and provide a documented stop/rollback path.

Do not use a user-specific interactive shortcut as the production control plane. Do not put tokens, private keys, certificate contents or OIDC client secrets in this repository, the command wrapper or an unprotected Task Scheduler argument list.

## Evidence boundary

Successful `-ValidateOnly` output is **deployment configuration evidence only**. It does not prove Acer boot behavior, Windows service reliability, thermal/charger behavior, power-loss recovery, disk encryption, firewall enforcement, kiosk escape prevention, real OIDC/mTLS, HIS integration or clinical validation. Those remain external gates in `P0_HARDWARE_BENCH_CHECKLIST.md`, `SECURITY_BASELINE.md` and the P1/P0 backlog.
