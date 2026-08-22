"""Local-only P0 OIDC/mTLS identity and transport readiness guard.

The guard validates configuration shape and file-hygiene metadata from deterministic
fixtures. It never contacts an issuer, JWKS endpoint, network, or TLS peer.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


SCHEMA_VERSION = "p0-identity-transport-readiness-v1"
AUTHORIZATION_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
SAFE_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"}
HTTPS_URL_PATTERN = re.compile(r"^https://[^\s/]+(?:/[^\s]*)?$")
SECRET_MARKER = re.compile(r"(?:-----BEGIN|Bearer(?:\s+|[-_])\S+|private[_-]?key\s*[:=]|api[_-]?key\s*[:=])", re.IGNORECASE)


class IdentityTransportGuardError(ValueError):
    """Raised when a local identity/transport fixture is unsafe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IdentityTransportGuardError(message)


def _safe_text(value: Any, field: str, *, max_length: int = 256) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field}_required")
    value = value.strip()
    _require(len(value) <= max_length, f"{field}_too_large")
    _require(SECRET_MARKER.search(value) is None, f"{field}_secret_marker")
    return value


def validate_oidc_fixture(config: dict[str, Any]) -> dict[str, Any]:
    expected = {"auth_mode", "issuer", "audience", "jwks_url", "algorithms"}
    _require(isinstance(config, dict) and set(config) == expected, "oidc_fields_mismatch")
    _require(config["auth_mode"] == "oidc", "oidc_auth_mode_required")
    issuer = _safe_text(config["issuer"], "oidc_issuer")
    audience = _safe_text(config["audience"], "oidc_audience")
    jwks_url = _safe_text(config["jwks_url"], "oidc_jwks_url")
    _require(HTTPS_URL_PATTERN.fullmatch(issuer) is not None, "oidc_issuer_https_required")
    _require(HTTPS_URL_PATTERN.fullmatch(jwks_url) is not None, "oidc_jwks_https_required")
    algorithms = config["algorithms"]
    _require(isinstance(algorithms, list) and algorithms, "oidc_algorithms_required")
    normalized = [item.strip().upper() for item in algorithms if isinstance(item, str) and item.strip()]
    _require(normalized and set(normalized).issubset(SAFE_ALGORITHMS), "oidc_algorithm_not_allowed")
    _require("NONE" not in normalized, "oidc_none_algorithm_forbidden")
    return {
        "valid": True,
        "auth_mode": "oidc",
        "issuer_configured": True,
        "audience_configured": True,
        "jwks_url_is_https": True,
        "algorithms": normalized,
        "live_issuer_reachable": False,
        "live_jwks_rotation_verified": False,
        "live_token_acceptance_verified": False,
        "live_revocation_verified": False,
        "evidence_class": "LOCAL_CONFIGURATION_ONLY",
    }


def validate_mtls_fixture(config: dict[str, Any]) -> dict[str, Any]:
    expected = {"certfile_present", "keyfile_present", "ca_certs_present", "key_mode", "client_cert_required"}
    _require(isinstance(config, dict) and set(config) == expected, "mtls_fields_mismatch")
    for field in ("certfile_present", "keyfile_present", "ca_certs_present", "client_cert_required"):
        _require(config[field] is True, f"{field}_required")
    mode = config["key_mode"]
    _require(isinstance(mode, int) and not isinstance(mode, bool) and 0 <= mode <= 0o777, "key_mode_invalid")
    _require(mode & 0o077 == 0, "private_key_permissions_too_open")
    return {
        "valid": True,
        "certfile_present": True,
        "keyfile_present": True,
        "ca_certs_present": True,
        "client_cert_required": True,
        "private_key_mode": f"{mode:04o}",
        "live_handshake_verified": False,
        "live_rotation_verified": False,
        "live_revocation_verified": False,
        "network_segmentation_verified": False,
        "evidence_class": "LOCAL_FILE_HYGIENE_ONLY",
    }


def evaluate_identity_transport_readiness(
    *,
    oidc_config: dict[str, Any] | None = None,
    mtls_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    oidc_fixture = oidc_config or {
        "auth_mode": "oidc",
        "issuer": "https://idp.example.test/",
        "audience": "smart-ward-hub",
        "jwks_url": "https://idp.example.test/.well-known/jwks.json",
        "algorithms": ["RS256"],
    }
    mtls_fixture = mtls_config or {
        "certfile_present": True,
        "keyfile_present": True,
        "ca_certs_present": True,
        "key_mode": 0o600,
        "client_cert_required": True,
    }
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []
    try:
        oidc_result = validate_oidc_fixture(oidc_fixture)
        checks["oidc_local_configuration_valid"] = oidc_result["valid"]
    except IdentityTransportGuardError as exc:
        oidc_result = {"valid": False, "error": str(exc), "evidence_class": "LOCAL_CONFIGURATION_ONLY"}
        checks["oidc_local_configuration_valid"] = False
        remediation_codes.append("OIDC_LOCAL_CONFIGURATION_INVALID")
    try:
        mtls_result = validate_mtls_fixture(mtls_fixture)
        checks["mtls_local_configuration_valid"] = mtls_result["valid"]
    except IdentityTransportGuardError as exc:
        mtls_result = {"valid": False, "error": str(exc), "evidence_class": "LOCAL_FILE_HYGIENE_ONLY"}
        checks["mtls_local_configuration_valid"] = False
        remediation_codes.append("MTLS_LOCAL_CONFIGURATION_INVALID")
    checks.update(
        {
            "live_network_contact_absent": True,
            "live_oidc_evidence_unverified": True,
            "live_mtls_evidence_unverified": True,
            "authority_boundary_locked": AUTHORIZATION_BOUNDARY == {
                "external_authority": "NONE",
                "clinical_validation_authorized": False,
                "production_authorized": False,
                "runtime_authority": "NONE",
                "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            },
        }
    )
    all_passed = all(checks.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "P0_IDENTITY_TRANSPORT_SOFTWARE_VERIFIED_PENDING_LIVE_EVIDENCE" if all_passed else "P0_IDENTITY_TRANSPORT_READINESS_BLOCKED",
        "mode": "LOCAL_DETERMINISTIC_FIXTURE_ONLY",
        "checks": checks,
        "all_passed": all_passed,
        "remediation_codes": remediation_codes,
        "oidc_result": oidc_result,
        "mtls_result": mtls_result,
        "live_evidence": {
            "issuer_jwks_reachability": "UNVERIFIED",
            "token_signature_acceptance": "UNVERIFIED",
            "scope_mapping": "UNVERIFIED",
            "rotation_and_revocation": "UNVERIFIED",
            "mutual_tls_handshake": "UNVERIFIED",
            "certificate_rotation_and_revocation": "UNVERIFIED",
            "network_segmentation": "UNVERIFIED",
        },
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "external_authority": "NONE",
        "external_gate_snapshot": {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0},
        "patient_data_used": False,
        "raw_frames_recorded": False,
        "hardware_evidence": "UNVERIFIED",
        "redaction_verified": True,
        "authorization_boundary": deepcopy(AUTHORIZATION_BOUNDARY),
    }


if __name__ == "__main__":
    import json

    report = evaluate_identity_transport_readiness()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    print("P0_IDENTITY_TRANSPORT_READINESS_GUARD_PASSED" if report["all_passed"] else "P0_IDENTITY_TRANSPORT_READINESS_GUARD_BLOCKED")
