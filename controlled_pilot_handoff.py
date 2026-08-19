from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


EXTERNAL_GATE_IDS = (
    "GV-01",
    "GV-02",
    "GV-03",
    "GV-04",
    "GV-05",
    "GV-06",
    "GV-07",
    "GV-08",
    "GV-09",
    "GV-10",
)
GATE_STATUSES = {"OPEN", "BLOCKED", "EVIDENCE_SUBMITTED", "PASSED", "REJECTED"}
HANDOFF_STATUSES = {"BLOCKED_PENDING_EXTERNAL_AUTHORIZATION", "READY_FOR_EXTERNAL_REVIEW"}


class ControlledPilotHandoffError(ValueError):
    pass


@dataclass(frozen=True)
class ControlledPilotHandoff:
    handoff_version: str
    handoff_id: str
    generated_at_utc: str
    product_status: str
    review_decision_status: str
    readiness_status: str
    gate_statuses: dict[str, str]
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    pilot_gate_status: str
    clinical_validation_authorized: bool = False
    production_authorized: bool = False
    runtime_authority: str = "NONE"

    def validate(self) -> "ControlledPilotHandoff":
        if self.handoff_version != "controlled-pilot-handoff-v1":
            raise ControlledPilotHandoffError("unsupported_handoff_version")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{5,127}", self.handoff_id):
            raise ControlledPilotHandoffError("invalid_handoff_id")
        try:
            timestamp = datetime.fromisoformat(self.generated_at_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ControlledPilotHandoffError("generated_at_invalid") from exc
        if timestamp.tzinfo is None:
            raise ControlledPilotHandoffError("generated_at_must_be_timezone_aware")
        if self.product_status not in {"controlled production prototype", "P0-hardened software baseline"}:
            raise ControlledPilotHandoffError("product_status_outside_claim_boundary")
        if self.review_decision_status not in {
            "BLOCKED_INCOMPLETE_EVIDENCE",
            "BLOCKED_PROVIDER_WINDOW",
            "BLOCKED_RUNTIME_ADAPTER",
            "REQUIRES_HUMAN_REVIEW",
            "ACCEPTED_FOR_EXTERNAL_REVIEW",
        }:
            raise ControlledPilotHandoffError("invalid_review_decision_status")
        if self.readiness_status not in {"NOT_READY", "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"}:
            raise ControlledPilotHandoffError("invalid_readiness_status")
        if set(self.gate_statuses) != set(EXTERNAL_GATE_IDS):
            raise ControlledPilotHandoffError("external_gate_matrix_incomplete")
        if any(status not in GATE_STATUSES for status in self.gate_statuses.values()):
            raise ControlledPilotHandoffError("invalid_external_gate_status")
        if not self.evidence_refs or any(not ref.strip() for ref in self.evidence_refs):
            raise ControlledPilotHandoffError("evidence_refs_required")
        if any(not blocker.strip() for blocker in self.blockers):
            raise ControlledPilotHandoffError("blocker_text_invalid")
        if self.pilot_gate_status not in HANDOFF_STATUSES:
            raise ControlledPilotHandoffError("invalid_pilot_gate_status")
        if self.clinical_validation_authorized is not False:
            raise ControlledPilotHandoffError("clinical_validation_authorization_forbidden")
        if self.production_authorized is not False:
            raise ControlledPilotHandoffError("production_authorization_forbidden")
        if self.runtime_authority != "NONE":
            raise ControlledPilotHandoffError("runtime_authority_forbidden")
        if self.readiness_status == "NOT_READY" and self.pilot_gate_status != "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION":
            raise ControlledPilotHandoffError("not_ready_requires_blocked_pilot_gate")
        if "BLOCKED" in self.gate_statuses.values() and self.pilot_gate_status != "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION":
            raise ControlledPilotHandoffError("blocked_external_gate_requires_blocked_pilot_gate")
        return self

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_controlled_pilot_handoff(
    *,
    handoff_id: str,
    review_decision: dict[str, Any],
    readiness_status: str,
    gate_statuses: dict[str, str],
    evidence_refs: list[str],
    blockers: list[str],
) -> ControlledPilotHandoff:
    pilot_gate_status = (
        "READY_FOR_EXTERNAL_REVIEW"
        if readiness_status == "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW" and review_decision.get("status") == "ACCEPTED_FOR_EXTERNAL_REVIEW" and all(status == "PASSED" for status in gate_statuses.values())
        else "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    )
    # Local software cannot convert any state into clinical or production authorization.
    handoff = ControlledPilotHandoff(
        handoff_version="controlled-pilot-handoff-v1",
        handoff_id=handoff_id,
        generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        product_status="controlled production prototype",
        review_decision_status=str(review_decision.get("status", "BLOCKED_INCOMPLETE_EVIDENCE")),
        readiness_status=readiness_status,
        gate_statuses=dict(gate_statuses),
        evidence_refs=tuple(evidence_refs),
        blockers=tuple(blockers),
        pilot_gate_status=pilot_gate_status,
    )
    return handoff.validate()


__all__ = [
    "ControlledPilotHandoff",
    "ControlledPilotHandoffError",
    "EXTERNAL_GATE_IDS",
    "build_controlled_pilot_handoff",
]
