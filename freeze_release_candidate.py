from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "evals/micro_rag/evidence/release-candidate-freeze-20260820.json"
SECRET_RE = re.compile(
    rb"BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}"
)
RUNTIME_NAMES = {
    "ward_hub.db",
    "ward_hub.db-shm",
    "ward_hub.db-wal",
    "audit_events.jsonl",
    "edge_telemetry_state.json",
    "forensic_anchors.jsonl",
}
TEXT_SUFFIXES = {".csv", ".css", ".example", ".html", ".ini", ".js", ".json", ".mako", ".md", ".py", ".service", ".sh", ".sql", ".svg", ".toml", ".txt", ".xml", ".yaml", ".yml"}
TEXT_NAMES = {".gitattributes", ".gitignore"}


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def revision_is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def canonical_bytes(path: Path) -> bytes:
    """Hash text content consistently when checked out with CRLF or LF."""
    raw = path.read_bytes()
    return raw.replace(b"\r\n", b"\n") if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES else raw


def sha256_path(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def classify(path: str) -> str:
    if path == "requirements.txt":
        return "dependency_manifest"
    if path.startswith("evals/") or path.endswith(".json"):
        return "evidence_or_machine_record"
    if path.endswith(".py") or path.endswith(".sh") or path in {"alembic.ini", ".env.example"}:
        return "source_or_runtime_config"
    if path.endswith(".md"):
        return "contract_or_governance_document"
    return "repository_asset"


def main() -> int:
    manifest_relative = str(OUTPUT.relative_to(ROOT))
    tracked = [
        item for item in run_git("ls-files").splitlines() if item and item != manifest_relative
    ]
    status = run_git("status", "--porcelain")
    head = run_git("rev-parse", "HEAD")
    remote = run_git("rev-parse", "origin/main")
    runtime_artifacts = sorted(
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file() and path.name in RUNTIME_NAMES
    )
    secret_hits: list[str] = []
    files: list[dict[str, object]] = []
    for relative in tracked:
        path = ROOT / relative
        raw = canonical_bytes(path)
        if SECRET_RE.search(raw):
            secret_hits.append(relative)
        files.append(
            {
                "path": relative,
                "classification": classify(relative),
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    checks = {
        "working_tree_clean_before_manifest": status == "",
        "head_matches_origin_main": head == remote or revision_is_ancestor(remote, head),
        "secret_marker_scan_pass": not secret_hits,
        "runtime_artifact_scan_pass": not runtime_artifacts,
        "tracked_file_hashes_generated": bool(files),
    }
    payload = {
        "schema_version": "smart-ward-hub-release-freeze-v1",
        "repository": "icezingza/smart-ward-hub",
        "freeze_created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": head,
        "origin_main_revision": remote,
        "manifest_path": str(OUTPUT.relative_to(ROOT)),
        "manifest_self_hash_excluded": True,
        "freeze_status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "secret_hits": secret_hits,
        "runtime_artifacts": runtime_artifacts,
        "authorization_boundary": {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
        "claim_boundary": {
            "valid": [
                "controlled production prototype",
                "P0-hardened software baseline",
                "functional verification passed",
                "pilot-ready foundation",
                "clinical validation pending",
            ],
            "forbidden_from_local_freeze": [
                "clinical-ready",
                "production-ready",
                "tamper-proof",
                "HIPAA/PDPA compliant 100%",
            ],
        },
        "external_gate_snapshot": {
            "blocked": 7,
            "open": 3,
            "evidence_submitted": 0,
            "passed": 0,
        },
        "files": files,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RELEASE_FREEZE_STATUS={payload['freeze_status']}")
    print(f"SOURCE_REVISION={head}")
    print(f"FILE_COUNT={len(files)}")
    print(f"OUTPUT={OUTPUT}")
    return 0 if payload["freeze_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
