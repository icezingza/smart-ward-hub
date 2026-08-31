import hashlib
import hmac
import json
import os
import sys

from config import settings

HMAC_SECRET_ENV = "SW_QR_HMAC_SECRET"
DEFAULT_HMAC_SECRET = "smart-ward-hub-dev-qr-secret"

def get_hmac_secret() -> str:
    """Retrieve the HMAC secret for QR verification."""
    secret = os.getenv(HMAC_SECRET_ENV, "").strip()
    if secret:
        return secret
    try:
        from gcp_secrets import get_secret
        gcp_val = get_secret(HMAC_SECRET_ENV)
        if gcp_val:
            return gcp_val
    except Exception:
        pass
    
    if settings.environment == "production":
        raise RuntimeError(f"Missing {HMAC_SECRET_ENV} in production environment. Refusing to fallback.")
    return DEFAULT_HMAC_SECRET


def verify_qr_payload(qr_payload: str) -> dict:
    """
    Parse and verify the HMAC signature of a patient QR payload.
    Returns the parsed payload dict if valid.
    Raises ValueError if invalid, malformed, or signature mismatch.
    """
    try:
        data = json.loads(qr_payload)
    except json.JSONDecodeError:
        raise ValueError("Payload is not valid JSON")

    required_keys = {"anonymous_id", "bed_id", "issued_at", "hmac_sig"}
    if not required_keys.issubset(data.keys()):
        raise ValueError("Payload missing required fields")

    provided_sig = data.pop("hmac_sig")
    
    # Reconstruct the strictly formatted JSON used for signing
    payload_to_sign = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":")
    )

    hmac_secret = get_hmac_secret()
    
    expected_sig = hmac.new(
        hmac_secret.encode("utf-8"),
        payload_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise ValueError("Invalid cryptographic signature in QR payload")

    # Restore the popped key for completeness if caller needs it
    data["hmac_sig"] = provided_sig
    return data
