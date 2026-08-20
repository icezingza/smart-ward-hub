from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9][A-Z0-9-]{1,}|\s+[0-9][A-Z0-9-]{1,})\b", re.IGNORECASE)
FORBIDDEN_CLAIMS = re.compile(r"\b(?:clinical-ready|production-ready|tamper-proof|clinical validated|hipaa/pdpa compliant 100%)\b", re.IGNORECASE)
VALID_GATE_STATES = {"OPEN", "BLOCKED", "EVIDENCE_SUBMITTED"}
VALID_OPERATIONS_STATES = {"NOT_READY", "READY_FOR_EXTERNAL_REVIEW", "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}


class ControlledPilotOperationsError(ValueError):
    pass


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ControlledPilotOperationsError("timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise ControlledPilotOperationsError("timestamp_must_be_timezone_aware")
    return parsed


@dataclass(frozen=True)
class BlockerRecord:
    blocker_id: str
    gate_id: str
    reason: str
    status: str = "BLOCKED"
    recorded_at_utc: str = ""
    reopened_at_utc: str | None = None

    def validate(self) -> "BlockerRecord":
        if not re.fullmatch(r"[A-Z0-9-]{4,64}", self.blocker_id):
            raise ControlledPilotOperationsError("blocker_id_invalid")
        if not re.fullmatch(r"GV-[0-9]{2}", self.gate_id):
            raise ControlledPilotOperationsError("blocker_gate_id_invalid")
        if not self.reason.strip() or RAW_ID.search(self.reason) or FORBIDDEN_CLAIMS.search(self.reason):
            raise ControlledPilotOperationsError("blocker_reason_invalid")
        if self.status not in {"BLOCKED", "OPEN"}:
            raise ControlledPilotOperationsError("blocker_status_invalid")
        _timestamp(self.recorded_at_utc)
        if self.reopened_at_utc is not None:
            _timestamp(self.reopened_at_utc)
            if self.status != "OPEN":
                raise ControlledPilotOperationsError("reopened_blocker_must_be_open")
        return self

    def reopen(self, reason: str, reopened_at_utc: str) -> "BlockerRecord":
        if self.status != "BLOCKED":
            raise ControlledPilotOperationsError("blocker_not_blocked")
        if not reason.strip() or RAW_ID.search(reason) or FORBIDDEN_CLAIMS.search(reason):
            raise ControlledPilotOperationsError("reopen_reason_invalid")
        _timestamp(reopened_at_utc)
        return BlockerRecord(
            blocker_id=self.blocker_id,
            gate_id=self.gate_id,
            reason=reason.strip(),
            status="OPEN",
            recorded_at_utc=self.recorded_at_utc,
            reopened_at_utc=reopened_at_utc,
        )


@dataclass(frozen=True)
class EvidenceManifestItem:
    evidence_id: str
    gate_id: str
    artifact_ref: str
    artifact_sha256: str
    evidence_class: str
    collected_at_utc: str
    prepared_by_role: str
    redaction_status: str
    chain_of_custody_ref: str
    independent_verification_required: bool = True

    def validate(self) -> "EvidenceManifestItem":
        if not re.fullmatch(r"[A-Za-z0-9._:-]{4,160}", self.evidence_id):
            raise ControlledPilotOperationsError("evidence_id_invalid")
        if not re.fullmatch(r"GV-[0-9]{2}", self.gate_id):
            raise ControlledPilotOperationsError("evidence_gate_id_invalid")
        if not self.artifact_ref.strip() or RAW_ID.search(self.artifact_ref):
            raise ControlledPilotOperationsError("artifact_ref_invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", self.artifact_sha256):
            raise ControlledPilotOperationsError("artifact_sha256_invalid")
        if self.evidence_class not in {"SOFTWARE_VERIFIED", "SIMULATION_ONLY", "EXTERNAL_UNVERIFIED", "CLINICAL_GOVERNANCE_UNVERIFIED", "BLOCKER_RECORD"}:
            raise ControlledPilotOperationsError("evidence_class_invalid")
        _timestamp(self.collected_at_utc)
        if not re.fullmatch(r"[a-z0-9._-]{3,80}", self.prepared_by_role):
            raise ControlledPilotOperationsError("prepared_by_role_invalid")
        if self.redaction_status != "PASS":
            raise ControlledPilotOperationsError("redaction_not_pass")
        if not self.chain_of_custody_ref.strip() or RAW_ID.search(self.chain_of_custody_ref):
            raise ControlledPilotOperationsError("chain_of_custody_ref_invalid")
        if self.independent_verification_required is not True:
            raise ControlledPilotOperationsError("independent_verification_required")
        return self


@dataclass(frozen=True)
class EvidenceManifest:
    manifest_version: str
    manifest_id: str
    generated_at_utc: str
    previous_manifest_hash: str | None
    items: tuple[EvidenceManifestItem, ...]
    claim_boundary: str

    def canonical_payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "manifest_version": self.manifest_version,
            "manifest_id": self.manifest_id,
            "generated_at_utc": self.generated_at_utc,
            "previous_manifest_hash": self.previous_manifest_hash,
            "items": [asdict(item) for item in self.items],
            "claim_boundary": self.claim_boundary,
        }

    def validate(self) -> "EvidenceManifest":
        if self.manifest_version != "controlled-pilot-manifest-v1":
            raise ControlledPilotOperationsError("manifest_version_invalid")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{5,127}", self.manifest_id):
            raise ControlledPilotOperationsError("manifest_id_invalid")
        _timestamp(self.generated_at_utc)
        if self.previous_manifest_hash is not None and not re.fullmatch(r"[a-f0-9]{64}", self.previous_manifest_hash):
            raise ControlledPilotOperationsError("previous_manifest_hash_invalid")
        if not self.items:
            raise ControlledPilotOperationsError("manifest_items_required")
        ids = [item.evidence_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ControlledPilotOperationsError("duplicate_evidence_id")
        for item in self.items:
            item.validate()
        if not self.claim_boundary.strip() or FORBIDDEN_CLAIMS.search(self.claim_boundary) or RAW_ID.search(self.claim_boundary):
            raise ControlledPilotOperationsError("claim_boundary_invalid")
        return self

    def manifest_hash(self) -> str:
        payload = json.dumps(self.canonical_payload(), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def simulated_detached_receipt(self, key_id: str) -> dict[str, str]:
        self.validate()
        if not re.fullmatch(r"[a-z0-9._-]{3,80}", key_id):
            raise ControlledPilotOperationsError("receipt_key_id_invalid")
        digest = hashlib.sha256(f"SIMULATED-RECEIPT|{key_id}|{self.manifest_hash()}".encode("utf-8")).hexdigest()
        return {
            "receipt_type": "SIGNED_STYLE_SIMULATION_NOT_CRYPTOGRAPHIC_SIGNATURE",
            "key_id": key_id,
            "manifest_hash": self.manifest_hash(),
            "receipt_digest": digest,
            "external_authority": "NONE",
        }


def build_manifest_item(
    *,
    evidence_id: str,
    gate_id: str,
    artifact_path: str | Path,
    evidence_class: str,
    collected_at_utc: str,
    prepared_by_role: str,
    chain_of_custody_ref: str,
) -> EvidenceManifestItem:
    path = Path(artifact_path)
    try:
        artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ControlledPilotOperationsError("artifact_unreadable") from exc
    item = EvidenceManifestItem(
        evidence_id=evidence_id,
        gate_id=gate_id,
        artifact_ref=path.as_posix(),
        artifact_sha256=artifact_sha256,
        evidence_class=evidence_class,
        collected_at_utc=collected_at_utc,
        prepared_by_role=prepared_by_role,
        redaction_status="PASS",
        chain_of_custody_ref=chain_of_custody_ref,
    )
    return item.validate()


@dataclass(frozen=True)
class OperationalGateDecision:
    state: str
    blockers: tuple[BlockerRecord, ...]
    manifest_hash: str
    clinical_validation_authorized: bool = False
    production_authorized: bool = False
    runtime_authority: str = "NONE"

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "blockers": [asdict(blocker) for blocker in self.blockers],
            "manifest_hash": self.manifest_hash,
            "clinical_validation_authorized": self.clinical_validation_authorized,
            "production_authorized": self.production_authorized,
            "runtime_authority": self.runtime_authority,
        }


def evaluate_operational_gate(
    *,
    gate_statuses: dict[str, str],
    readiness_status: str,
    review_decision_status: str,
    manifest: EvidenceManifest,
    blockers: tuple[BlockerRecord, ...],
) -> OperationalGateDecision:
    manifest.validate()
    if set(gate_statuses) != {f"GV-{index:02d}" for index in range(1, 11)}:
        raise ControlledPilotOperationsError("complete_10_gate_matrix_required")
    if any(status not in VALID_GATE_STATES for status in gate_statuses.values()):
        raise ControlledPilotOperationsError("gate_status_invalid")
    if readiness_status not in {"NOT_READY", "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"}:
        raise ControlledPilotOperationsError("readiness_status_invalid")
    if review_decision_status not in {
        "BLOCKED_INCOMPLETE_EVIDENCE",
        "BLOCKED_PROVIDER_WINDOW",
        "BLOCKED_RUNTIME_ADAPTER",
        "REQUIRES_HUMAN_REVIEW",
        "ACCEPTED_FOR_EXTERNAL_REVIEW",
    }:
        raise ControlledPilotOperationsError("review_decision_status_invalid")
    for blocker in blockers:
        blocker.validate()
    has_gate_blocker = "BLOCKED" in gate_statuses.values()
    has_open_gate = "OPEN" in gate_statuses.values()
    if readiness_status == "NOT_READY" or review_decision_status != "ACCEPTED_FOR_EXTERNAL_REVIEW" or has_gate_blocker or blockers:
        state = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    elif has_open_gate:
        state = "READY_FOR_EXTERNAL_REVIEW"
    else:
        state = "READY_FOR_EXTERNAL_REVIEW"
    return OperationalGateDecision(
        state=state,
        blockers=tuple(blockers),
        manifest_hash=manifest.manifest_hash(),
    )


__all__ = [
    "BlockerRecord",
    "ControlledPilotOperationsError",
    "EvidenceManifest",
    "EvidenceManifestItem",
    "OperationalGateDecision",
    "build_manifest_item",
    "evaluate_operational_gate",
]
