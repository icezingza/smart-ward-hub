"""Read-only consolidated internal handoff index.

This module navigates already-generated local evidence packages. It does not
submit evidence externally, authorize deployment, mutate runtime state, or
change any external gate.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from cross_package_evidence_binding import (
    APPROVAL_PATH,
    DURABLE_PATH,
    FREEZE_PATH,
    TRANSCRIPT_PATH,
    check_repository,
)


SCHEMA_VERSION = "smart-ward-consolidated-internal-handoff-v1"
INDEX_REF = "handoff-index:worker-recovery-001"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{2,127}$")
LOCKED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
LOCKED_EXTERNAL_GATE_SNAPSHOT = {
    "blocked": 7,
    "evidence_submitted": 0,
    "open": 3,
    "passed": 0,
}
REQUIRED_PACKAGES = (
    ("worker_recovery_transcript", TRANSCRIPT_PATH, "transcript"),
    ("worker_recovery_approval_readback", APPROVAL_PATH, "approval"),
    ("durable_worker_replay", DURABLE_PATH, "durable"),
    ("cross_package_binding", Path("evals/micro_rag/evidence/cross-package-binding-local.json"), "binding"),
)


class HandoffIndexValidationError(ValueError):
    """Raised when a consolidated internal handoff index fails closed."""


@dataclass(frozen=True, slots=True)
class HandoffIndexResult:
    decision: str
    remediation_codes: tuple[str, ...]
    index: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "index": deepcopy(self.index),
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HandoffIndexValidationError(message)


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_revision(value: Any) -> bool:
    return isinstance(value, str) and HEX40.fullmatch(value) is not None


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _valid_ref(value: Any) -> bool:
    return isinstance(value, str) and SAFE_REF.fullmatch(value) is not None


def _load_json(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffIndexValidationError(f"invalid_json:{relative}") from exc
    _require(isinstance(payload, dict), f"json_must_be_object:{relative}")
    return payload


def _package_navigation(
    binding: Mapping[str, Any],
    package_hashes: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    refs = binding.get("refs", {})
    revisions = binding.get("source_revisions", {})
    hashes = binding.get("artifact_hashes", {})
    package_hashes = package_hashes or {}
    rows: list[dict[str, Any]] = []
    for package_id, relative, ref_key in REQUIRED_PACKAGES:
        rows.append(
            {
                "package_id": package_id,
                "artifact_path": relative.as_posix(),
                "artifact_ref": refs.get(ref_key, f"artifact:{package_id}"),
                "artifact_sha256": package_hashes.get(ref_key, hashes.get(ref_key, "")),
                "source_revision": revisions.get(ref_key, binding.get("source_revision", "") if ref_key == "binding" else ""),
                "status": "BOUND" if ref_key != "binding" else binding.get("decision", "RECONCILIATION_REQUIRED"),
            }
        )
    return rows


def evaluate_index(
    *,
    binding: Mapping[str, Any],
    freeze: Mapping[str, Any],
    package_hashes: Mapping[str, str] | None = None,
    current_revision: str | None = None,
) -> HandoffIndexResult:
    """Build a consolidated index or return a fail-closed reconciliation result."""
    codes: list[str] = []
    binding_decision = binding.get("decision")
    binding_codes = binding.get("remediation_codes")
    checks = binding.get("checks")
    boundary = binding.get("authorization_boundary")
    freeze_source = freeze.get("source_revision")
    origin_revision = freeze.get("origin_main_revision")
    freeze_status = freeze.get("freeze_status")

    if binding_decision != "BOUND" or binding_codes != ["EVIDENCE_PACKAGES_BOUND"]:
        codes.append("CROSS_PACKAGE_BINDING_NOT_BOUND")
    if not isinstance(checks, Mapping) or not checks or not all(value is True for value in checks.values()):
        codes.append("CROSS_PACKAGE_CHECKS_NOT_ALL_PASS")
    if boundary != LOCKED_BOUNDARY:
        codes.append("AUTHORIZATION_BOUNDARY_MUTATED")
    if freeze_status != "PASS":
        codes.append("FREEZE_NOT_PASS")
    if freeze.get("external_gate_snapshot") != LOCKED_EXTERNAL_GATE_SNAPSHOT:
        codes.append("EXTERNAL_GATE_SNAPSHOT_MUTATED")
    if not _valid_revision(freeze_source) or not _valid_revision(origin_revision):
        codes.append("FREEZE_SOURCE_REVISION_INVALID")
    elif freeze_source != origin_revision:
        codes.append("FREEZE_SOURCE_ORIGIN_MISMATCH")
    if current_revision is not None and not _valid_revision(current_revision):
        codes.append("CURRENT_REVISION_INVALID")
    if binding.get("read_only") is not True or binding.get("external_transmission_performed") is not False:
        codes.append("BINDING_READ_ONLY_BOUNDARY_INVALID")
    if binding.get("redaction_verified") is not True:
        codes.append("BINDING_REDACTION_NOT_VERIFIED")
    claim = binding.get("claim_boundary")
    if not isinstance(claim, Mapping) or claim.get("production_ready") is not False or claim.get("clinical_validation") != "PENDING":
        codes.append("CLAIM_BOUNDARY_MUTATED")

    freeze_files = {
        item.get("path"): item
        for item in freeze.get("files", [])
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    }
    for package_id, relative, ref_key in REQUIRED_PACKAGES:
        entry = freeze_files.get(relative.as_posix())
        if not isinstance(entry, Mapping):
            codes.append(f"FREEZE_MISSING_{package_id.upper()}")
            continue
        if package_hashes is not None and ref_key in package_hashes and entry.get("sha256") != package_hashes[ref_key]:
            codes.append(f"FREEZE_HASH_MISMATCH_{package_id.upper()}")

    package_rows = _package_navigation(binding, package_hashes)
    for row in package_rows:
        if not _valid_ref(row["artifact_ref"]):
            codes.append(f"PACKAGE_REF_INVALID_{row['package_id'].upper()}")
        if not _valid_sha(row["artifact_sha256"]):
            codes.append(f"PACKAGE_HASH_INVALID_{row['package_id'].upper()}")
        if not _valid_revision(row["source_revision"]):
            codes.append(f"PACKAGE_REVISION_INVALID_{row['package_id'].upper()}")

    codes = list(dict.fromkeys(codes))
    decision = "BOUND" if not codes else "RECONCILIATION_REQUIRED"
    if decision == "BOUND":
        codes = ["HANDOFF_INDEX_BOUND"]

    index = {
        "schema_version": SCHEMA_VERSION,
        "index_ref": INDEX_REF,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "remediation_codes": list(codes),
        "evidence_navigation": package_rows,
        "binding_snapshot": {
            "artifact_ref": "binding:cross-package-001",
            "artifact_sha256": _sha256_json(dict(binding)),
            "decision": binding_decision,
            "binding_codes": binding_codes,
            "freeze_source_revision": binding.get("freeze_source_revision"),
        },
        "freeze": {
            "manifest_path": freeze.get("manifest_path", FREEZE_PATH.as_posix()),
            "freeze_status": freeze_status,
            "source_revision": freeze_source,
            "origin_main_revision": origin_revision,
            "tracked_file_count": len(freeze.get("files", [])) if isinstance(freeze.get("files"), list) else 0,
            "external_gate_snapshot": deepcopy(freeze.get("external_gate_snapshot", {})),
        },
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED" if decision == "BOUND" else "PENDING_RECONCILIATION",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
        "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
    }
    return HandoffIndexResult(decision=decision, remediation_codes=tuple(codes), index=index)


def build_index(root: Path) -> HandoffIndexResult:
    """Load repository artifacts and build the internal index without mutation."""
    binding = _load_json(root, Path("evals/micro_rag/evidence/cross-package-binding-local.json"))
    freeze = _load_json(root, FREEZE_PATH)
    package_hashes = {
        "transcript": _file_sha(root / TRANSCRIPT_PATH),
        "approval": _file_sha(root / APPROVAL_PATH),
        "durable": _file_sha(root / DURABLE_PATH),
        "binding": _file_sha(root / Path("evals/micro_rag/evidence/cross-package-binding-local.json")),
    }
    try:
        import subprocess
        current_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        current_revision = None
    return evaluate_index(
        binding=binding,
        freeze=freeze,
        package_hashes=package_hashes,
        current_revision=current_revision,
    )


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    result = build_index(Path(__file__).resolve().parent)
    print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
    print("CONSOLIDATED_INTERNAL_HANDOFF_INDEX_BOUND" if result.decision == "BOUND" else "CONSOLIDATED_INTERNAL_HANDOFF_INDEX_RECONCILIATION_REQUIRED")
