from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any


SAFE_REF = re.compile(r"[A-Za-z0-9._:/-]{1,200}")
SHA256 = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]?\s*[A-Z0-9-]+\b", re.IGNORECASE)
ALLOWED_CLASSES = {
    "SOFTWARE_VERIFIED",
    "SIMULATION_ONLY",
    "EXTERNAL_UNVERIFIED",
    "CLINICAL_GOVERNANCE_UNVERIFIED",
    "BLOCKER_RECORD",
}
FORBIDDEN_CLASSES = {"CLINICAL_VALIDATED", "PRODUCTION_READY", "TAMPER_PROOF"}
VALID_GATE_IDS = {f"GV-{index:02d}" for index in range(1, 11)}


class GV10EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceEntry:
    evidence_id: str
    gate_id: str
    artifact_ref: str
    artifact_sha256: str
    evidence_class: str
    collected_at_utc: str
    prepared_by_role: str
    source_boundary: str
    redaction_status: str
    chain_of_custody_ref: str
    independent_verification_required: bool = True

    def validate(self) -> None:
        for name, value in (
            ("evidence_id", self.evidence_id),
            ("artifact_ref", self.artifact_ref),
            ("source_boundary", self.source_boundary),
            ("chain_of_custody_ref", self.chain_of_custody_ref),
        ):
            if not SAFE_REF.fullmatch(value) or RAW_ID.search(value):
                raise GV10EvidenceError(f"unsafe_{name}")
        if self.gate_id not in VALID_GATE_IDS:
            raise GV10EvidenceError("unknown_gate_id")
        if not SHA256.fullmatch(self.artifact_sha256):
            raise GV10EvidenceError("artifact_sha256_required")
        evidence_class = self.evidence_class.strip().upper()
        if evidence_class in FORBIDDEN_CLASSES:
            raise GV10EvidenceError("forbidden_evidence_class")
        if evidence_class not in ALLOWED_CLASSES:
            raise GV10EvidenceError("unsupported_evidence_class")
        if not self.prepared_by_role.strip():
            raise GV10EvidenceError("prepared_by_role_required")
        if self.redaction_status != "PASS":
            raise GV10EvidenceError("redaction_pass_required")
        if self.independent_verification_required is not True:
            raise GV10EvidenceError("independent_verification_required")
        try:
            parsed = datetime.fromisoformat(self.collected_at_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GV10EvidenceError("invalid_collected_at") from exc
        if parsed.tzinfo is None:
            raise GV10EvidenceError("collected_at_must_be_timezone_aware")


@dataclass
class GV10EvidenceDossier:
    dossier_id: str
    review_scope: str
    prepared_by_role: str
    independent_reviewer_role: str = "independent_reviewer"
    claim_boundary: str = "INDEPENDENT_REVIEW_INPUT_UNVERIFIED"
    entries: list[EvidenceEntry] = field(default_factory=list)

    def validate(self) -> None:
        if not SAFE_REF.fullmatch(self.dossier_id) or RAW_ID.search(self.dossier_id):
            raise GV10EvidenceError("unsafe_dossier_id")
        if not self.review_scope.strip() or not self.prepared_by_role.strip():
            raise GV10EvidenceError("dossier_scope_and_preparer_required")
        if not self.independent_reviewer_role.strip():
            raise GV10EvidenceError("independent_reviewer_role_required")
        if "UNVERIFIED" not in self.claim_boundary.upper():
            raise GV10EvidenceError("dossier_claim_boundary_must_remain_unverified")
        if not self.entries:
            raise GV10EvidenceError("evidence_entries_required")
        seen: set[str] = set()
        for entry in self.entries:
            entry.validate()
            if entry.evidence_id in seen:
                raise GV10EvidenceError("duplicate_evidence_id")
            seen.add(entry.evidence_id)

    def add_entry(self, entry: EvidenceEntry) -> None:
        self.validate() if self.entries else None
        entry.validate()
        if entry.evidence_id in {item.evidence_id for item in self.entries}:
            raise GV10EvidenceError("duplicate_evidence_id")
        self.entries.append(entry)

    def review_readiness(self) -> dict[str, Any]:
        self.validate()
        gate_ids = sorted({entry.gate_id for entry in self.entries})
        classes = sorted({entry.evidence_class.strip().upper() for entry in self.entries})
        return {
            "dossier_id": self.dossier_id,
            "entry_count": len(self.entries),
            "gate_ids_covered": gate_ids,
            "evidence_classes": classes,
            "ready_for_independent_review": True,
            "independent_reviewer_role": self.independent_reviewer_role,
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "evidence_class": "INDEPENDENT_REVIEW_INPUT_UNVERIFIED",
        }


def build_gv10_template() -> GV10EvidenceDossier:
    dossier = GV10EvidenceDossier(
        dossier_id="smart-ward-gv10-review-v1",
        review_scope="Independent review of Smart Ward Hub software evidence and external-validation blockers",
        prepared_by_role="engineering_evidence_coordinator",
    )
    return dossier
