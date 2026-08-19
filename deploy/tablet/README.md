# Tablet-only deployment templates

These files are reference templates for a dedicated Smart Ward Hub Tablet appliance. They are not a universal medical-device installation script and must be adapted to the selected tablet operating system, display session, user ID, storage layout, hospital network and power supervision.

## Intended boot behavior

1. The operating system boots into a dedicated device-owner/kiosk account.
2. `smart-ward-hub.service` starts the local FastAPI Edge service on loopback.
3. The kiosk UI service opens Chromium at `http://127.0.0.1:8080/kiosk`.
4. The kiosk page calls the local bootstrap endpoint and displays restored non-PII session state.
5. The UI exposes freshness, trust, offline and reconciliation flags instead of assuming restored state is current.

## Required adaptation before use

The operator must create the `smartward` service account, install the project under `/opt/smart-ward-hub`, create the virtual environment and dependencies, configure `/etc/smart-ward-hub/smart-ward-hub.env`, select correct read/write paths, and apply the current Alembic migration before the pilot. The `DISPLAY` value and graphical-session integration in the kiosk service must be adapted to the target OS.

Do not expose port 8080 to the ward network merely because the kiosk UI works locally. If remote administration or an external display is required, add a separate authenticated gateway with OIDC/mTLS and explicit scopes. The local kiosk bootstrap is restricted to loopback in the reference implementation.

## Minimum Tablet gate

The selected device must pass cold boot, service restart, kiosk escape prevention, encrypted storage, checkpoint recovery, stale-state indication, reset-pending recovery, power interruption, storage failure, offline operation, update/rollback and manual clinical fallback tests. Passing these software/device gates does not establish clinical readiness, regulatory compliance or hardware security certification.
