from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from evidence_reconciliation import EvidenceReconciliationError, default_paths, reconcile_packages
from freeze_integrity_monitor import revision_is_ancestor
from export_evidence_reconciliation import export


ROOT = Path(__file__).resolve().parent


def expect_error(callback) -> None:
    try:
        callback()
    except EvidenceReconciliationError:
        return
    raise AssertionError("expected EvidenceReconciliationError")


def copied_fixture_root(tmp: Path) -> Path:
    freeze_path = default_paths(ROOT)["freeze_path"]
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    revision = freeze.get("source_revision")
    assert isinstance(revision, str) and revision
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        archive = subprocess.run(["git", "archive", revision], cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            try:
                tar.extractall(tmp, filter="data")  # nosec B202
            except TypeError:
                tar.extractall(tmp)  # nosec B202
    except Exception:
        for item in ROOT.iterdir():
            if item.name.startswith(".git") or item.name == "tmp" or item.name == ".gemini":
                continue
            if item.is_dir():
                shutil.copytree(item, tmp / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, tmp / item.name)
    archived_freeze = tmp / freeze_path.relative_to(ROOT)
    archived_freeze.write_bytes(freeze_path.read_bytes())
    return tmp


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repository = Path(directory) / "git-lineage"
        repository.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=repository, check=True)
        (repository / "a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repository, check=True)
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
        (repository / "b.txt").write_text("b\n", encoding="utf-8")
        subprocess.run(["git", "add", "b.txt"], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "next"], cwd=repository, check=True)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
        assert revision_is_ancestor(repository, base, head) is True
        assert revision_is_ancestor(repository, head, base) is False
        assert revision_is_ancestor(repository, repository / "missing", head) is False
    print("[Reconciliation] Isolated local Git ancestry helper is fail-closed: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        root = copied_fixture_root(Path(directory))
        paths = default_paths(root)
        result = reconcile_packages(**paths)
        assert result["reconciliation_status"] == "RECONCILED_WITH_EXTERNAL_BLOCKERS"
        assert result["gate_decision"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
        assert result["execution_permitted"] is False
        assert result["submission_permitted"] is False
        assert result["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
        assert result["authorization_boundary"]["external_authority"] == "NONE"
        assert result["states"]["wave_e_execution_permitted"] is False
        assert result["states"]["wave_e_external_validation_started"] is False
        assert any(finding["finding_id"] == "SOURCE_NONIDENTICAL_WAVE4" for finding in result["findings"])
        assert result["source_revision_lineage"]["wave4"]["ancestor_verified"] is False
        assert result["source_revision_lineage"]["wave4"]["relation"] == "NON_ANCESTOR_BLOCKED"
        print("[Reconciliation] Current package set reconciles with explicit external blockers: PASSED")

        reviewer_path = paths["reviewer_path"]
        reviewer = json.loads(reviewer_path.read_text(encoding="utf-8"))
        reviewer["authorization_boundary"]["production_authorized"] = True
        reviewer_path.write_text(json.dumps(reviewer, indent=2) + "\n", encoding="utf-8")
        expect_error(lambda: reconcile_packages(**paths))
        print("[Reconciliation] Authorization mutation is rejected: PASSED")

        reviewer["authorization_boundary"]["production_authorized"] = False
        reviewer_path.write_text(json.dumps(reviewer, indent=2) + "\n", encoding="utf-8")
        freeze = json.loads(paths["freeze_path"].read_text(encoding="utf-8"))
        freeze["files"][0]["sha256"] = "0" * 64
        paths["freeze_path"].write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
        expect_error(lambda: reconcile_packages(**paths))
        print("[Reconciliation] Release-freeze artifact hash mismatch is rejected: PASSED")

        root = copied_fixture_root(Path(directory) / "state-drift")
        paths = default_paths(root)
        wave_e_path = paths["wave_e_path"]
        wave_e = json.loads(wave_e_path.read_text(encoding="utf-8"))
        wave_e["packet_status"] = "READY_FOR_EXTERNAL_EXECUTION"
        wave_e_path.write_text(json.dumps(wave_e, indent=2) + "\n", encoding="utf-8")
        expect_error(lambda: reconcile_packages(**paths))
        print("[Reconciliation] Wave E execution escalation is rejected: PASSED")

        exported_path = Path(directory) / "reconciliation-export.json"
        exported = export(root=ROOT, output=exported_path)
        exported_payload = json.loads(exported_path.read_text(encoding="utf-8"))
        assert exported["gate_decision"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
        assert exported_payload["execution_permitted"] is False
        assert exported_payload["submission_permitted"] is False
        print("[Reconciliation] Frozen-source exporter produces locked consolidated snapshot: PASSED")

    print("EVIDENCE_RECONCILIATION_TESTS_PASSED")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise
