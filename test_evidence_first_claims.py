from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
APPROVED_TERMS = (
    "Cryptographically Verifiable Tamper-Evident Audit Trail",
    "Hospital-Controlled Data Boundary",
    "Traceability & Forensic Readiness",
)
CLAIM_SURFACES = (
    Path("README.md"),
    Path("architecture.md"),
    Path("docs/EVIDENCE_FIRST_CLAIMS_POLICY.md"),
    Path("docs/PRODUCT_BOUNDARY.md"),
    Path("SMART_WARD_STATUS_PRESENTATION_CONTENT.md"),
)
AFFIRMATIVE_OVERCLAIMS = (
    re.compile(
        r"\b(?:is|are|provides?|delivers?|guarantees?)\s+(?:a\s+)?(?:100%\s+)?(?:tamper[- ]proof|air[- ]gapped)(?:\s+100%)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:prevents?|eliminates?|guarantees? protection from)\s+(?:all\s+)?(?:lawsuits?|litigation|liability)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:ป้องกัน|รับประกัน).{0,30}(?:การฟ้องร้อง|ความรับผิด|ผลทางกฎหมาย).{0,12}100%"),
)


def find_affirmative_overclaims(text: str) -> list[str]:
    return [match.group(0) for pattern in AFFIRMATIVE_OVERCLAIMS for match in pattern.finditer(text)]


def test_canonical_claim_surfaces_use_approved_terms() -> None:
    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in CLAIM_SURFACES)
    for term in APPROVED_TERMS:
        assert term in combined
    assert find_affirmative_overclaims(combined) == []


def test_affirmative_marketing_overclaims_fail_detection() -> None:
    unsafe = " ".join(
        (
            "The product is Tamper-Proof 100%.",
            "The ward network is 100% Air-Gapped.",
            "This platform prevents all lawsuits.",
            "ระบบป้องกันการฟ้องร้องได้ 100%",
        )
    )
    assert len(find_affirmative_overclaims(unsafe)) == 4


def run() -> None:
    test_canonical_claim_surfaces_use_approved_terms()
    test_affirmative_marketing_overclaims_fail_detection()
    print("[EvidenceFirst] CISO claim vocabulary and overclaim guard: PASSED")
    print("EVIDENCE_FIRST_CLAIMS_TESTS_PASSED")


if __name__ == "__main__":
    run()
