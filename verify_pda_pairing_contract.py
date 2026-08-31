from schemas import PairingRequest
from pydantic import ValidationError

payload = {
    "bed_id": "BED-04",
    "patient_token": "anon-9032-uuid",
    "device_uid": "C6:04:A1:B2:C3:D4",
    "placement_position": "WRIST",
}

model = PairingRequest.model_validate(payload)
assert model.bed_no == "BED-04"
assert model.device_id == "C6:04:A1:B2:C3:D4"
assert model.patient_token == "anon-9032-uuid"
assert model.placement_position == "WRIST"

try:
    PairingRequest.model_validate({**payload, "unexpected": "must-reject"})
except ValidationError:
    pass
else:
    raise AssertionError("unknown pairing fields must be rejected")

for raw in ("HN-2026-0001", "AN-123456"):
    try:
        PairingRequest.model_validate({**payload, "patient_token": raw})
    except ValidationError:
        pass
    else:
        raise AssertionError(f"raw identity token was accepted: {raw}")

print("PDA_PAIRING_CONTRACT_PASSED")
