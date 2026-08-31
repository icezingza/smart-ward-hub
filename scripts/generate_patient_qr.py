#!/usr/bin/env python3
"""
generate_patient_qr.py — Anonymous Patient QR Code Provisioning CLI
====================================================================
Generates unique, privacy-preserving QR codes for patient bed assignments.
Each QR encodes a signed JSON payload containing:
  - anonymous_id  : UUID4 (no PII linkage)
  - bed_id        : ward bed identifier
  - issued_at     : ISO-8601 timestamp
  - hmac_sig      : HMAC-SHA256 integrity signature

Usage:
    python scripts/generate_patient_qr.py --bed-id B-01 --output ./qr_codes/
    python scripts/generate_patient_qr.py --bed-id B-01 --bed-id B-02 --bed-id B-03
    python scripts/generate_patient_qr.py --batch 1 30 --output ./qr_codes/
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import qrcode  # type: ignore[import-untyped]
except ImportError:
    qrcode = None


HMAC_SECRET_ENV = "SW_QR_HMAC_SECRET"
DEFAULT_HMAC_SECRET = "smart-ward-hub-dev-qr-secret"  # dev-only fallback


def _get_hmac_secret() -> str:
    """Load HMAC secret from env or GCP Secret Manager fallback."""
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
    print(f"[WARN] {HMAC_SECRET_ENV} not set — using dev-only fallback. "
          f"DO NOT use in production!", file=sys.stderr)
    return DEFAULT_HMAC_SECRET


def generate_patient_payload(bed_id: str, hmac_secret: str) -> dict:
    """Create a signed anonymous patient payload."""
    anonymous_id = str(uuid.uuid4())
    issued_at = datetime.now(timezone.utc).isoformat()
    payload_data = json.dumps(
        {"anonymous_id": anonymous_id, "bed_id": bed_id, "issued_at": issued_at},
        sort_keys=True,
        separators=(",", ":"),
    )
    sig = hmac.new(
        hmac_secret.encode("utf-8"),
        payload_data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "anonymous_id": anonymous_id,
        "bed_id": bed_id,
        "issued_at": issued_at,
        "hmac_sig": sig,
    }


def render_qr_image(payload: dict, output_dir: Path) -> Path:
    """Render QR code as PNG image and return the file path."""
    if qrcode is None:
        print("[ERROR] qrcode library not installed. Run: pip install qrcode[pil]",
              file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"patient_qr_{payload['bed_id']}_{payload['anonymous_id'][:8]}.png"
    filepath = output_dir / filename

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(payload, sort_keys=True))
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(str(filepath))
    return filepath


def render_qr_text(payload: dict) -> None:
    """Print QR payload as JSON to stdout (no image dependency)."""
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate anonymous patient QR codes for Smart Ward Hub"
    )
    parser.add_argument(
        "--bed-id", action="append", default=[],
        help="Bed identifier (can be repeated). e.g. --bed-id B-01 --bed-id B-02"
    )
    parser.add_argument(
        "--batch", nargs=2, type=int, metavar=("START", "END"),
        help="Generate QR codes for beds B-{START:02d} through B-{END:02d}"
    )
    parser.add_argument(
        "--output", type=str, default="./qr_codes",
        help="Output directory for QR PNG images (default: ./qr_codes)"
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="Print JSON payloads to stdout instead of generating images"
    )
    args = parser.parse_args()

    # Collect bed IDs
    bed_ids: list[str] = list(args.bed_id)
    if args.batch:
        start, end = args.batch
        for i in range(start, end + 1):
            bed_ids.append(f"B-{i:02d}")

    if not bed_ids:
        parser.error("Specify --bed-id or --batch to generate QR codes.")

    hmac_secret = _get_hmac_secret()
    output_dir = Path(args.output)
    generated: list[dict] = []

    for bed_id in bed_ids:
        payload = generate_patient_payload(bed_id, hmac_secret)
        generated.append(payload)

        if args.json_only:
            render_qr_text(payload)
        else:
            filepath = render_qr_image(payload, output_dir)
            print(f"[OK] {bed_id} -> {filepath}")

    # Write manifest
    if not args.json_only:
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(generated, f, indent=2, ensure_ascii=False)
        print(f"\n[MANIFEST] {len(generated)} QR codes -> {manifest_path}")


if __name__ == "__main__":
    main()
