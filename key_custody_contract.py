from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any


HEX64 = re.compile(r"^[0-9a-f]{64}$")


class KeyCustodyError(ValueError):
    pass


@dataclass(frozen=True)
class CustodyAttestation:
    evidence_id: str
    manufacturer_ca_verified: bool
    secure_element_present: bool
    private_key_non_exportable: bool


@dataclass
class ProvisioningRecord:
    device_id: str
    key_id: str
    algorithm: str
    public_key_fingerprint: str
    status: str
    previous_key_id: str | None
    custody_backend: str
    manufacturer_ca_verified: bool
    secure_element_present: bool
    private_key_non_exportable: bool
    evidence_status: str
    created_at_utc: str
    activated_at_utc: str | None = None
    revoked_at_utc: str | None = None
    lost_at_utc: str | None = None


class KeyCustodyRegistry:
    """Contract-level registry; never stores private key material."""

    def __init__(
        self,
        *,
        require_dual_control: bool = True,
        require_hardware_attestation: bool = True,
        allow_software_fixture: bool = False,
        clock: callable | None = None,
    ) -> None:
        self.require_dual_control = require_dual_control
        self.require_hardware_attestation = require_hardware_attestation
        self.allow_software_fixture = allow_software_fixture
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: dict[str, ProvisioningRecord] = {}

    def _now(self) -> str:
        return self._clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def register_public_key(
        self,
        *,
        device_id: str,
        key_id: str,
        algorithm: str,
        public_key_fingerprint: str,
        previous_key_id: str | None = None,
        private_key_material: str | None = None,
        custody_backend: str = "software-test-only",
    ) -> ProvisioningRecord:
        if private_key_material is not None:
            raise KeyCustodyError("private_key_material_must_never_enter_registry")
        if not device_id or not key_id or algorithm != "Ed25519" or not HEX64.fullmatch(public_key_fingerprint):
            raise KeyCustodyError("invalid_public_key_registration")
        if key_id in self._records:
            raise KeyCustodyError("duplicate_key_id")
        record = ProvisioningRecord(
            device_id=device_id,
            key_id=key_id,
            algorithm=algorithm,
            public_key_fingerprint=public_key_fingerprint,
            status="PROVISIONING",
            previous_key_id=previous_key_id,
            custody_backend=custody_backend,
            manufacturer_ca_verified=False,
            secure_element_present=False,
            private_key_non_exportable=False,
            evidence_status="UNVERIFIED",
            created_at_utc=self._now(),
        )
        self._records[key_id] = record
        return record

    def activate(self, key_id: str, *, approver_ids: list[str], attestation: CustodyAttestation) -> ProvisioningRecord:
        record = self._get(key_id)
        if record.status != "PROVISIONING":
            raise KeyCustodyError(f"activation_not_allowed_from_{record.status}")
        distinct_approvers = {item for item in approver_ids if item}
        if self.require_dual_control and len(distinct_approvers) < 2:
            raise KeyCustodyError("dual_control_approval_required")
        hardware_verified = (
            attestation.manufacturer_ca_verified
            and attestation.secure_element_present
            and attestation.private_key_non_exportable
        )
        if self.require_hardware_attestation and not hardware_verified and not self.allow_software_fixture:
            raise KeyCustodyError("hardware_attestation_required")
        record.status = "ACTIVE"
        record.activated_at_utc = self._now()
        record.manufacturer_ca_verified = attestation.manufacturer_ca_verified
        record.secure_element_present = attestation.secure_element_present
        record.private_key_non_exportable = attestation.private_key_non_exportable
        record.evidence_status = "VERIFIED" if hardware_verified else "UNVERIFIED"
        return record

    def suspend(self, key_id: str) -> ProvisioningRecord:
        record = self._get(key_id)
        if record.status in {"REVOKED", "LOST"}:
            raise KeyCustodyError("terminal_credential_cannot_suspend")
        record.status = "SUSPENDED"
        return record

    def revoke(self, key_id: str, *, reason: str) -> ProvisioningRecord:
        if not reason.strip():
            raise KeyCustodyError("revocation_reason_required")
        record = self._get(key_id)
        if record.status == "REVOKED":
            return record
        record.status = "REVOKED"
        record.revoked_at_utc = self._now()
        return record

    def mark_lost(self, key_id: str, *, incident_id: str) -> ProvisioningRecord:
        if not incident_id.strip():
            raise KeyCustodyError("lost_device_incident_required")
        record = self._get(key_id)
        record.status = "LOST"
        record.lost_at_utc = self._now()
        record.revoked_at_utc = record.lost_at_utc
        return record

    def complete_rotation(self, *, new_key_id: str, old_key_id: str) -> tuple[ProvisioningRecord, ProvisioningRecord]:
        new_record = self._get(new_key_id)
        old_record = self._get(old_key_id)
        if new_record.status != "ACTIVE" or old_record.device_id != new_record.device_id:
            raise KeyCustodyError("rotation_requires_active_same_device_key")
        if new_record.previous_key_id != old_key_id:
            raise KeyCustodyError("rotation_link_mismatch")
        if old_record.status not in {"ACTIVE", "SUSPENDED"}:
            raise KeyCustodyError("old_key_not_rotatable")
        old_record.status = "SUSPENDED"
        return new_record, old_record

    def snapshot(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in sorted(self._records.values(), key=lambda item: item.key_id)]

    def _get(self, key_id: str) -> ProvisioningRecord:
        if key_id not in self._records:
            raise KeyCustodyError("unknown_key_id")
        return self._records[key_id]
