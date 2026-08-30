"""Cross-package binding checker for internal worker recovery evidence.

The checker is intentionally read-only. It validates that the redacted worker
recovery transcript, approval/read-back record, durable worker replay evidence,
and release-freeze manifest describe the same software-only rehearsal and that
freeze-tracked artifact bytes match the checked-in evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
TRANSCRIPT_PATH = Path("evals/micro_rag/evidence/worker-recovery-transcript-local.json")
APPROVAL_PATH = Path("evals/micro_rag/evidence/worker-recovery-approval-local.json")
DURABLE_PATH = Path("evals/micro_rag/evidence/durable-worker-replay-local.json")
FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_TEXT_SUFFIXES = {".json", ".md", ".py", ".txt", ".yaml", ".yml"}


class BindingDecision(StrEnum):
    BOUND = "BOUND"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class BindingCode(StrEnum):
    EVIDENCE_PACKAGES_BOUND = "EVIDENCE_PACKAGES_BOUND"
    FREEZE_ARTIFACT_NOT_LISTED = "FREEZE_ARTIFACT_NOT_LISTED"
    FREEZE_ARTIFACT_HASH_MISMATCH = "FREEZE_ARTIFACT_HASH_MISMATCH"
    FREEZE_BOUNDARY_MUTATED = "FREEZE_BOUNDARY_MUTATED"
    TRANSCRIPT_INTEGRITY_INVALID = "TRANSCRIPT_INTEGRITY_INVALID"
    TRANSCRIPT_SCHEMA_MISMATCH = "TRANSCRIPT_SCHEMA_MISMATCH"
    APPROVAL_TRANSCRIPT_REF_MISMATCH = "APPROVAL_TRANSCRIPT_REF_MISMATCH"
    APPROVAL_TRANSCRIPT_HASH_MISMATCH = "APPROVAL_TRANSCRIPT_HASH_MISMATCH"
    APPROVAL_QUEUE_REF_MISMATCH = "APPROVAL_QUEUE_REF_MISMATCH"
    APPROVAL_QUEUE_HASH_MISMATCH = "APPROVAL_QUEUE_HASH_MISMATCH"
    DURABLE_REPLAY_BOUNDARY_MISMATCH = "DURABLE_REPLAY_BOUNDARY_MISMATCH"
    SOURCE_REVISION_MISSING = "SOURCE_REVISION_MISSING"
    SOURCE_REVISION_INVALID = "SOURCE_REVISION_INVALID"
    SOURCE_REVISION_NOT_ANCESTOR_OF_FREEZE = "SOURCE_REVISION_NOT_ANCESTOR_OF_FREEZE"


@dataclass(frozen=True, slots=True)
class BindingResult:
    decision: str
    remediation_codes: tuple[str, ...]
    checks: dict[str, bool]
    refs: dict[str, str]
    source_revisions: dict[str, str]
    freeze_source_revision: str
    read_only: bool
    external_transmission_performed: bool
    authorization_boundary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "remediation_codes": list(self.remediation_codes),
            "checks": dict(self.checks),
            "refs": dict(self.refs),
            "source_revisions": dict(self.source_revisions),
            "freeze_source_revision": self.freeze_source_revision,
            "read_only": self.read_only,
            "external_transmission_performed": self.external_transmission_performed,
            "authorization_boundary": dict(self.authorization_boundary),
        }


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() in CANONICAL_TEXT_SUFFIXES:
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _load_json(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"evidence_json_invalid:{relative}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"evidence_json_not_object:{relative}")
    return payload


def _locked_boundary(payload: Mapping[str, Any]) -> bool:
    boundary = payload.get("authorization_boundary")
    if not isinstance(boundary, Mapping):
        return False
    return (
        boundary.get("external_authority") == "NONE"
        and boundary.get("clinical_validation_authorized") is False
        and boundary.get("production_authorized") is False
        and boundary.get("runtime_authority") == "NONE"
        and boundary.get("pilot_gate_status") == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    )


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _valid_revision(value: Any) -> bool:
    return isinstance(value, str) and HEX40.fullmatch(value) is not None


def _ancestor(root: Path, child: str, ancestor: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, child],
            cwd=root,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return completed.returncode == 0


def _freeze_file_index(freeze: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    files = freeze.get("files")
    if not isinstance(files, list):
        return {}
    return {
        item.get("path"): item
        for item in files
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    }


def _add_code(codes: list[str], code: BindingCode) -> None:
    if code.value not in codes:
        codes.append(code.value)


def evaluate_bindings(
    *,
    transcript: Mapping[str, Any],
    approval: Mapping[str, Any],
    durable: Mapping[str, Any],
    freeze: Mapping[str, Any],
    artifact_hashes: Mapping[str, str] | None = None,
    git_root: Path | None = None,
    verify_revision_ancestry: bool = True,
) -> BindingResult:
    """Evaluate all cross-package bindings without mutating any input."""
    codes: list[str] = []
    checks: dict[str, bool] = {}
    refs: dict[str, str] = {}
    revisions: dict[str, str] = {}
    freeze_source = str(freeze.get("source_revision", ""))
    boundary = freeze.get("authorization_boundary")
    boundary_ok = (
        boundary == {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        }
    )
    checks["freeze_boundary_locked"] = boundary_ok
    if not boundary_ok:
        _add_code(codes, BindingCode.FREEZE_BOUNDARY_MUTATED)
    checks["freeze_source_revision_valid"] = _valid_revision(freeze_source)
    if not checks["freeze_source_revision_valid"]:
        _add_code(codes, BindingCode.SOURCE_REVISION_INVALID)

    freeze_files = _freeze_file_index(freeze)
    for label, relative in (
        ("transcript", TRANSCRIPT_PATH),
        ("approval", APPROVAL_PATH),
        ("durable", DURABLE_PATH),
    ):
        entry = freeze_files.get(relative.as_posix())
        actual_hash = (artifact_hashes or {}).get(label)
        listed_ok = isinstance(entry, Mapping)
        checks[f"freeze_lists_{label}"] = listed_ok
        if not listed_ok:
            _add_code(codes, BindingCode.FREEZE_ARTIFACT_NOT_LISTED)
            continue
        if actual_hash is not None:
            hash_ok = entry.get("sha256") == actual_hash
            checks[f"freeze_hash_matches_{label}"] = hash_ok
            if not hash_ok:
                _add_code(codes, BindingCode.FREEZE_ARTIFACT_HASH_MISMATCH)

    transcript_integrity = transcript.get("transcript_integrity_valid") is True
    checks["transcript_integrity_valid"] = transcript_integrity
    if not transcript_integrity:
        _add_code(codes, BindingCode.TRANSCRIPT_INTEGRITY_INVALID)
    checks["transcript_schema_valid"] = transcript.get("schema_version") == "smart-ward-worker-recovery-transcript-v1"
    if not checks["transcript_schema_valid"]:
        _add_code(codes, BindingCode.TRANSCRIPT_SCHEMA_MISMATCH)
    transcript_ref = transcript.get("correlation_ref")
    refs["transcript_ref"] = str(transcript_ref)
    transcript_events = transcript.get("transcript")
    transcript_hash = _canonical_sha(transcript_events)
    approval_payload = approval.get("approval")
    if not isinstance(approval_payload, Mapping):
        approval_payload = {}
    approval_ref = approval_payload.get("transcript_ref")
    refs["approval_transcript_ref"] = str(approval_ref)
    checks["approval_transcript_ref_matches"] = approval_ref == transcript_ref
    if not checks["approval_transcript_ref_matches"]:
        _add_code(codes, BindingCode.APPROVAL_TRANSCRIPT_REF_MISMATCH)
    checks["approval_transcript_hash_matches"] = approval_payload.get("transcript_sha256") == transcript_hash
    if not checks["approval_transcript_hash_matches"]:
        _add_code(codes, BindingCode.APPROVAL_TRANSCRIPT_HASH_MISMATCH)

    last_event = transcript_events[-1] if isinstance(transcript_events, list) and transcript_events else {}
    last_details = last_event.get("details") if isinstance(last_event, Mapping) else {}
    if not isinstance(last_details, Mapping):
        last_details = {}
    expected_queue_ref = last_details.get("backup_ref")
    expected_queue_hash = _canonical_sha(dict(last_details))
    refs["transcript_queue_backup_ref"] = str(expected_queue_ref)
    refs["approval_queue_backup_ref"] = str(approval_payload.get("queue_backup_ref"))
    checks["approval_queue_ref_matches"] = approval_payload.get("queue_backup_ref") == expected_queue_ref
    if not checks["approval_queue_ref_matches"]:
        _add_code(codes, BindingCode.APPROVAL_QUEUE_REF_MISMATCH)
    checks["approval_queue_hash_matches"] = approval_payload.get("queue_binding_sha256") == expected_queue_hash
    if not checks["approval_queue_hash_matches"]:
        _add_code(codes, BindingCode.APPROVAL_QUEUE_HASH_MISMATCH)

    durable_boundary = (
        durable.get("mode") == "SOFTWARE_FIXTURE"
        and durable.get("read_only_external_boundary") is True
        and durable.get("external_transmission_performed") is False
        and durable.get("clinical_state_mutation_performed") is False
        and durable.get("runtime_replay_executed") is False
        and durable.get("authorization_boundary") == {
            "external_authority": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
        }
    )
    checks["durable_replay_boundary_locked"] = durable_boundary
    if not durable_boundary:
        _add_code(codes, BindingCode.DURABLE_REPLAY_BOUNDARY_MISMATCH)

    for label, payload in (("transcript", transcript), ("approval", approval), ("durable", durable)):
        revision = payload.get("source_revision")
        if revision is None and label == "durable":
            _add_code(codes, BindingCode.SOURCE_REVISION_MISSING)
            checks[f"{label}_source_revision_present"] = False
            continue
        checks[f"{label}_source_revision_present"] = _valid_revision(revision)
        if not checks[f"{label}_source_revision_present"]:
            _add_code(codes, BindingCode.SOURCE_REVISION_INVALID)
            continue
        revisions[label] = str(revision)
        if verify_revision_ancestry and git_root is not None and checks["freeze_source_revision_valid"]:
            ancestor_ok = _ancestor(git_root, freeze_source, str(revision))
            checks[f"{label}_source_revision_ancestor"] = ancestor_ok
            if not ancestor_ok:
                _add_code(codes, BindingCode.SOURCE_REVISION_NOT_ANCESTOR_OF_FREEZE)

    read_only = (
        transcript.get("read_only") is True
        and approval.get("read_only") is True
        and durable.get("read_only_external_boundary") is True
    )
    checks["all_packages_read_only"] = read_only
    external_transmission = any(
        payload.get("external_transmission_performed") is True
        for payload in (transcript, approval, durable)
    )
    checks["no_external_transmission"] = not external_transmission
    if external_transmission:
        _add_code(codes, BindingCode.DURABLE_REPLAY_BOUNDARY_MISMATCH)

    if not codes:
        _add_code(codes, BindingCode.EVIDENCE_PACKAGES_BOUND)
    decision = BindingDecision.BOUND.value if codes == [BindingCode.EVIDENCE_PACKAGES_BOUND.value] else BindingDecision.RECONCILIATION_REQUIRED.value
    return BindingResult(
        decision=decision,
        remediation_codes=tuple(codes),
        checks=checks,
        refs=refs,
        source_revisions=revisions,
        freeze_source_revision=freeze_source,
        read_only=True,
        external_transmission_performed=False,
        authorization_boundary={
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
    )


def check_repository(root: Path = ROOT, *, verify_revision_ancestry: bool = True) -> dict[str, Any]:
    """Load repository artifacts, verify freeze-listed hashes, and evaluate bindings."""
    transcript = _load_json(root, TRANSCRIPT_PATH)
    approval = _load_json(root, APPROVAL_PATH)
    durable = _load_json(root, DURABLE_PATH)
    freeze = _load_json(root, FREEZE_PATH)
    artifact_hashes = {
        "transcript": _file_sha256(root / TRANSCRIPT_PATH),
        "approval": _file_sha256(root / APPROVAL_PATH),
        "durable": _file_sha256(root / DURABLE_PATH),
    }
    result = evaluate_bindings(
        transcript=transcript,
        approval=approval,
        durable=durable,
        freeze=freeze,
        artifact_hashes=artifact_hashes,
        git_root=root,
        verify_revision_ancestry=verify_revision_ancestry,
    )
    return {
        "evidence_type": "CROSS_PACKAGE_EVIDENCE_BINDING",
        "schema_version": "smart-ward-cross-package-binding-v1",
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "checks": result.checks,
        "refs": result.refs,
        "source_revisions": result.source_revisions,
        "freeze_source_revision": result.freeze_source_revision,
        "artifact_hashes": artifact_hashes,
        "read_only": True,
        "external_transmission_performed": False,
        "authorization_boundary": result.authorization_boundary,
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED" if result.decision == BindingDecision.BOUND.value else "PENDING_RECONCILIATION",
            "clinical_validation": "PENDING",
            "production_ready": False,
        },
    }


if __name__ == "__main__":
    report = check_repository()
    print(json.dumps(report, sort_keys=True, indent=2))
    print("CROSS_PACKAGE_EVIDENCE_BINDING_BOUND" if report["decision"] == BindingDecision.BOUND.value else "CROSS_PACKAGE_EVIDENCE_BINDING_RECONCILIATION_REQUIRED")
