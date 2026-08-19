# Smart Ward Hub — P1 Host Hardening Checklist

**Target:** Acer Spin N17H2 Fixed Hub candidate
**Status:** Checklist prepared; physical host execution pending

This checklist converts the security baseline into host-level controls. A checked software template or read-only inventory is not evidence that the Acer host is hardened.

| Control | Required state | Evidence required | Current status |
|---|---|---|---|
| Dedicated service identity | Non-admin account or service identity runs the Edge process | Windows account/group transcript and access review | Pending Acer |
| Source/runtime separation | Code is read-only; database, checkpoint and logs live outside source tree | Path and ACL transcript | Template prepared |
| Disk encryption | Approved encrypted volume protects runtime state | Windows encryption status and key-custody record | Unverified |
| Firewall | Only explicitly required local/management paths are allowed; loopback service is not ward-exposed | Firewall export and port scan from approved segment | Unverified |
| API docs | `SW_ENABLE_DOCS=false` in pilot | Readiness report | Software validator prepared |
| Host binding | FastAPI binds to `127.0.0.1` for local kiosk reference | Process/listening-socket transcript | Template prepared |
| Authentication | OIDC selected; static token mode limited to bench/development | Redacted environment/config transcript | Real IdP pending |
| mTLS | Test CA, client/server identity and rotation policy configured for HIS path | Handshake/renewal/revocation transcript | Unverified |
| Time | Trusted time source and bounded clock skew | Time-sync and clock-drift evidence | Unverified |
| Patch state | OS and runtime patch levels approved by host owner | Patch inventory and change record | Unverified |
| Service recovery | Auto-start, restart, stop and rollback are documented | Task Scheduler/service transcript and failure drill | Template prepared |
| Backup | Encrypted destination, manifest, checksum and retention configured | Successful backup and isolated restore transcript | Software baseline; real destination pending |
| Power | Charger/battery, sleep/hibernate and controlled power interruption are tested | Physical bench transcript | Unverified |
| Privacy | Screen angle, kiosk escape prevention, ports and removable media are reviewed | Site survey and human-factors evidence | Unverified |
| Monitoring | Health, disk, backup freshness, auth errors and sync queue are observable | Daily preflight and alert evidence | Runbook prepared |

## Stop conditions

Stop deployment if the runtime path is inside the source tree, API docs are enabled, the service binds to a non-loopback address without an approved gateway, static credentials are embedded in a script, the database is not on an approved encrypted volume, the backup cannot be restored to an isolated target, or the operator cannot identify a rollback version.

## Claim boundary

Completing this checklist in software or on paper does not establish **clinical-ready**, **tamper-proof**, **HIPAA/PDPA compliant 100%** or **production-ready** status. It supports the narrower claim **pilot deployment configuration prepared; host and clinical validation pending**.
