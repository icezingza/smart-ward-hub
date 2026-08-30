# Smart Ward Hub System Identity

This repository's technical identity is fixed for audit and deployment communication:

| Field | Canonical value |
|---|---|
| System | `Smart Ward Hub` |
| Product/code name | `IPD Smart Sentinel` |
| Version | `2.0.0` |
| Default database | `ward_hub.db` |
| API framework | FastAPI |
| Primary persistence | SQLite WAL |

The runtime identity is defined in `system_identity.py`, used by `config.py` and `main.py`, and exposed through the API metadata and `/health`. Environment variables may provide an explicitly approved deployment label, but they do not change the repository identity or version contract.

Unrelated brand or product names are out of scope for this technical repository. They must not appear in technical claims, API metadata, deployment instructions, evidence manifests or audit handoff materials.

This identity freeze does not claim clinical validation, production authorization, regulatory certification or legal readiness.
