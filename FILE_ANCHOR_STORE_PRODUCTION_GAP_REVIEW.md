# FileAnchorStore — Production-Readiness Gap Review

**Review target:** `edge_controls.py:128-154`, `main.py:1915-1926`, `test_residual_controls.py:138-160`
**Classification:** local software evidence review; not a production certification

## Current behavior

`FileAnchorStore` appends a minimal JSONL record under a process-local `RLock`, flushes the file and optionally calls `os.fsync()`. It returns only a boolean. The record is explicitly labelled `local_append_only_adapter`. The current regression confirms that a file is created with this label, but does not verify readback, field validity, idempotency, duplicate behavior, permission policy, failure translation, recovery after partial writes, or independent immutability.

`main.py` treats the result as `anchored` versus `local_only`, and `/api/v1/forensics/verify` verifies only the internal SHA-256 chain. The API does not verify a local anchor record or an external receipt during forensic verification.

## Gap matrix

| ID | Severity | Gap | Why it matters | Required remediation |
|---|---|---|---|---|
| FA-001 | Critical residual | Same-host JSONL is not an independent trust boundary | An attacker controlling the Hub host may modify or delete both package and anchor | Use an independently administered append-only/WORM service with authenticated transport and receipt verification |
| FA-002 | High | No request validation | Invalid package IDs, hashes or chain tips can be written | Validate positive package ID and canonical lowercase SHA-256 fields |
| FA-003 | High | Boolean-only result | Callers cannot verify provider identity, receipt identity or exact package/hash binding | Return a structured local receipt; preserve `AnchorStore` compatibility through a separate receipt-capable interface |
| FA-004 | High | No idempotency key | Retry after timeout can create duplicate anchors or ambiguous evidence | Derive stable idempotency key from exact package ID, block hash and chain tip |
| FA-005 | High | No readback/verification path | A successful write does not prove the record can be parsed or matches the requested chain tip | Add safe readback and verification for local records; do not equate it with external immutability |
| FA-006 | High | No path/permission policy | Anchor file may be placed inside source tree or be readable/writable by unintended users | Require an approved runtime path, restrictive ACL/permissions and host-level review |
| FA-007 | Medium | Partial-line and corruption handling absent | Crash during append may leave an invalid JSONL line | Use length/checksum framing or quarantine invalid lines and emit an operator-visible failure |
| FA-008 | Medium | No retention, rotation or monitoring contract | The file can grow without controlled retention and failures may remain silent | Define retention/legal hold, rotation, capacity monitoring and alerting |
| FA-009 | High residual | Forensic verify endpoint ignores anchor evidence | Internal chain verification can be mistaken for cross-boundary verification | Report local/external anchor status separately and require receipt verification for an external claim |
| FA-010 | High residual | No independent time or key custody | Local `anchored_at` is host time and is not a trusted timestamp | Use provider timestamp, authenticated transport and independently governed key custody |

## Recommended status

The correct status is **Implemented local append-only software baseline; external anchor unverified**. Hardening the local file improves data hygiene and operational diagnostics but does not convert it into external WORM or tamper-proof evidence.

## Production gate

A production deployment may use a local anchor only as a best-effort local evidence layer while the external anchor is unavailable, provided the UI and audit records say `LOCAL_ONLY` or `EXTERNAL_UNVERIFIED` and the runbook defines outage/reconciliation behavior. It must not report `EXTERNAL_VERIFIED` from a local file write.


## Post-hardening software result

The local adapter now validates package/hash inputs, rejects paths inside the source tree when a source root is supplied, writes a deterministic idempotency key and record hash, returns a structured local receipt, supports safe readback verification, avoids duplicate local records on replay and preserves readable legacy v1 records. `test_file_anchor_store.py` covers these controls plus tamper and malformed-input behavior.

These changes improve the local software baseline but do not close FA-001, FA-008, FA-009 or FA-010. Host ACLs, encrypted storage, log/anchor rotation, capacity monitoring, independent service identity, trusted timestamp, retention/legal hold and a separately administered WORM service remain external gates.
