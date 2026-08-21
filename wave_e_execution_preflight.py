from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


SCHEMA_VERSION = "wave-e-execution-preflight-v1"
COORDINATION_STATE = "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"
EVIDENCE_CLASS = "EXTERNAL_UNVERIFIED"
CRITERIA = (
    "E-01",
    "E-02",
    "E-03",
    "E-04",
    "E-05",
    "E-06",
    "E-07",
    "E-08",
    "E-09",
    "E-10",
)
ROLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
REF_PATTERN = re.compile(r"^[a-z][a-z0-9._:/-]{2,127}$")
SOURCE_REVISION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}$")
FORBIDDEN_MARKERS = re.compile(
    r"(?i)(patient[_ -]?id|patient[_ -]?token|patient[_ -]?name|hospital[_ -]?number|\bhn\b|\bmrn\b|national[_ -]?id|bearer|private[_ -]?key|secret|password|api[_ -]?key)"
)


class WaveEPreflightError(ValueError):
    pass


@dataclass(frozen=True)
class EntryCriterion:
    criterion_id: str
    asserted: bool
    evidence_ref: str | None
    owner_role: str
    notes: str = ""

    def validate(self) -> "EntryCriterion":
        if self.criterion_id not in CRITERIA:
            raise WaveEPreflightError("criterion_id_not_allowlisted")
        if not isinstance(self.asserted, bool):
            raise WaveEPreflightError(f"{self.criterion_id}:asserted_must_be_boolean")
        if not ROLE_PATTERN.fullmatch(self.owner_role):
            raise WaveEPreflightError(f"{self.criterion_id}:owner_role_invalid")
        if self.evidence_ref is not None:
            if not REF_PATTERN.fullmatch(self.evidence_ref) or FORBIDDEN_MARKERS.search(self.evidence_ref):
                raise WaveEPreflightError(f"{self.criterion_id}:evidence_ref_invalid")
        if not isinstance(self.notes, str) or len(self.notes) > 512 or FORBIDDEN_MARKERS.search(self.notes):
            raise WaveEPreflightError(f"{self.criterion_id}:notes_invalid")
        if self.asserted and not self.evidence_ref:
            raise WaveEPreflightError(f"{self.criterion_id}:asserted_requires_evidence_ref")
        return self


@dataclass(frozen=True)
class WaveEExecutionPreflight:
    package_revision: str
    created_at_utc: str
    prepared_by_role: str
    external_owner_role: str
    independent_verifier_role: str
    stop_authority_role: str
    recovery_approver_role: str
    authorization_snapshot: dict[str, Any]
    criteria: tuple[EntryCriterion, ...]
    source_revision: str
    evidence_class: str = EVIDENCE_CLASS
    schema_version: str = SCHEMA_VERSION
    coordination_state: str = COORDINATION_STATE
    execution_permitted: bool = False

    def validate(self) -> "WaveEExecutionPreflight":
        if self.schema_version != SCHEMA_VERSION:
            raise WaveEPreflightError("schema_version_invalid")
        if self.evidence_class != EVIDENCE_CLASS:
            raise WaveEPreflightError("evidence_class_invalid")
        if self.coordination_state != COORDINATION_STATE:
            raise WaveEPreflightError("coordination_state_invalid")
        for name, value in (
            ("package_revision", self.package_revision),
            ("source_revision", self.source_revision),
        ):
            pattern = SOURCE_REVISION_PATTERN if name == "source_revision" else REF_PATTERN
            if not isinstance(value, str) or not pattern.fullmatch(value) or FORBIDDEN_MARKERS.search(value):
                raise WaveEPreflightError(f"{name}_invalid")
        if not isinstance(self.created_at_utc, str):
            raise WaveEPreflightError("created_at_utc_invalid")
        try:
            created = datetime.fromisoformat(self.created_at_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise WaveEPreflightError("created_at_utc_invalid") from exc
        if created.tzinfo is None or created.utcoffset() is None:
            raise WaveEPreflightError("created_at_utc_must_be_timezone_aware")
        roles = {
            "prepared_by_role": self.prepared_by_role,
            "external_owner_role": self.external_owner_role,
            "independent_verifier_role": self.independent_verifier_role,
            "stop_authority_role": self.stop_authority_role,
            "recovery_approver_role": self.recovery_approver_role,
        }
        for name, role in roles.items():
            if not ROLE_PATTERN.fullmatch(role):
                raise WaveEPreflightError(f"{name}_invalid")
        if len(set(roles.values())) != len(roles):
            raise WaveEPreflightError("authority_roles_must_be_distinct")
        if not isinstance(self.execution_permitted, bool) or self.execution_permitted is not False:
            raise WaveEPreflightError("execution_permitted_must_remain_false")
        self._validate_authorization_snapshot()
        if not isinstance(self.criteria, tuple) or len(self.criteria) != len(CRITERIA):
            raise WaveEPreflightError("criteria_must_contain_exactly_ten_records")
        criterion_ids = [criterion.criterion_id for criterion in self.criteria]
        if set(criterion_ids) != set(CRITERIA) or len(criterion_ids) != len(set(criterion_ids)):
            raise WaveEPreflightError("criteria_must_cover_each_entry_once")
        for criterion in self.criteria:
            criterion.validate()
        return self

    def _validate_authorization_snapshot(self) -> None:
        expected = {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        }
        if set(self.authorization_snapshot) != set(expected):
            raise WaveEPreflightError("authorization_snapshot_schema_invalid")
        if self.authorization_snapshot != expected:
            raise WaveEPreflightError("authorization_boundary_mutation_rejected")

    @property
    def asserted_criteria(self) -> tuple[str, ...]:
        return tuple(sorted(criterion.criterion_id for criterion in self.criteria if criterion.asserted))

    @property
    def missing_criteria(self) -> tuple[str, ...]:
        return tuple(criterion for criterion in CRITERIA if criterion not in self.asserted_criteria)

    @property
    def external_execution_preconditions_present(self) -> bool:
        return not self.missing_criteria

    def validate_and_summarize(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "coordination_state": self.coordination_state,
            "evidence_class": self.evidence_class,
            "package_revision": self.package_revision,
            "source_revision": self.source_revision,
            "asserted_criteria": list(self.asserted_criteria),
            "missing_criteria": list(self.missing_criteria),
            "external_execution_preconditions_present": self.external_execution_preconditions_present,
            "execution_permitted": False,
            "external_validation_started": False,
            "authorization_snapshot": dict(self.authorization_snapshot),
            "claim_boundary": "EXTERNAL_UNVERIFIED_PENDING_OWNER_APPOINTMENT",
        }

    def canonical_payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "evidence_class": self.evidence_class,
            "coordination_state": self.coordination_state,
            "package_revision": self.package_revision,
            "created_at_utc": self.created_at_utc,
            "prepared_by_role": self.prepared_by_role,
            "external_owner_role": self.external_owner_role,
            "independent_verifier_role": self.independent_verifier_role,
            "stop_authority_role": self.stop_authority_role,
            "recovery_approver_role": self.recovery_approver_role,
            "authorization_snapshot": dict(self.authorization_snapshot),
            "criteria": [asdict(criterion) for criterion in sorted(self.criteria, key=lambda item: item.criterion_id)],
            "source_revision": self.source_revision,
            "execution_permitted": False,
        }

    def package_hash(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def export_handoff_packet(self) -> dict[str, Any]:
        summary = self.validate_and_summarize()
        packet = {
            "packet_schema": "wave-e-owner-appointment-handoff-v1",
            "packet_status": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT",
            "package_hash": self.package_hash(),
            "preflight": summary,
            "required_external_actions": [
                "appoint_external_authorization_service_owner",
                "appoint_identity_and_transport_owners",
                "appoint_independent_verifier_and_evidence_custodian",
                "sign_scope_window_expiry_rollback_and_stop_record",
                "provision_isolated_nonproduction_endpoint_and_test_identity",
                "provide_independent_custody_and_readback_path",
            ],
            "execution_prohibited_until": [
                "external_owner_appointment_is_signed",
                "test_window_and_scope_are_signed",
                "endpoint_identity_transport_acl_and_custody_are_independently verified",
                "no_authorization_snapshot_is_rechecked",
            ],
        }
        return packet


def build_empty_preflight(*, package_revision: str, source_revision: str, prepared_by_role: str = "integration_owner") -> WaveEExecutionPreflight:
    roles = (
        prepared_by_role,
        "external_service_owner",
        "independent_verifier",
        "stop_authority",
        "recovery_approver",
    )
    preflight = WaveEExecutionPreflight(
        package_revision=package_revision,
        created_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        prepared_by_role=roles[0],
        external_owner_role=roles[1],
        independent_verifier_role=roles[2],
        stop_authority_role=roles[3],
        recovery_approver_role=roles[4],
        authorization_snapshot={
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
        criteria=tuple(
            EntryCriterion(criterion_id=criterion_id, asserted=False, evidence_ref=None, owner_role=roles[1])
            for criterion_id in CRITERIA
        ),
        source_revision=source_revision,
    )
    return preflight.validate()


__all__ = [
    "COORDINATION_STATE",
    "CRITERIA",
    "EVIDENCE_CLASS",
    "EntryCriterion",
    "SCHEMA_VERSION",
    "WaveEExecutionPreflight",
    "WaveEPreflightError",
    "build_empty_preflight",
]
