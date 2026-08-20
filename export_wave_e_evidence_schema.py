from __future__ import annotations

import json
from pathlib import Path

from external_authorization_api_wave_e_evidence import (
    DOSSIER_TRANSITIONS,
    DossierState,
    WaveEEvidenceBundle,
    WaveEEvidenceRecord,
)


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "evals/micro_rag/evidence/wave-e-evidence-schema-v1.json"


def build_schema() -> dict:
    transitions = {
        state.value: sorted(target.value for target in targets)
        for state, targets in DOSSIER_TRANSITIONS.items()
    }
    return {
        "schema_id": "wave-e-evidence-v1",
        "bundle_schema_id": "wave-e-evidence-bundle-v1",
        "contract_version": "external-auth-sim-v2",
        "evidence_class": "EXTERNAL_UNVERIFIED",
        "authorization_boundary": {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        },
        "dossier_state_machine": {
            "states": [state.value for state in DossierState],
            "transitions": transitions,
            "terminal_states": [DossierState.CLOSED_NO_AUTHORIZATION.value],
        },
        "record_schema": WaveEEvidenceRecord.model_json_schema(),
        "bundle_schema": WaveEEvidenceBundle.model_json_schema(),
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WAVE_E_EVIDENCE_SCHEMA_WRITTEN {OUTPUT}")


if __name__ == "__main__":
    main()
