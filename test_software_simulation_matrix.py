from pathlib import Path
import subprocess

from software_simulation_matrix import EXTERNAL_GATES, SOFTWARE_DOMAINS, run_matrix


def successful_runner(*args, **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="pass", stderr="")


def run() -> None:
    report = run_matrix(execute=False)
    assert report["execution_mode"] == "PLAN_ONLY"
    assert report["software_simulation_passed"] is False
    assert report["patient_data_used"] is False
    assert report["hardware_contacted"] is False
    assert report["external_network_contacted"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    assert len(report["software_domains"]) == len(SOFTWARE_DOMAINS) == 10
    assert len(report["external_unverified_gates"]) == len(EXTERNAL_GATES) == 6
    assert all(item["status"] == "NOT_EXECUTED" for item in report["software_domains"])
    print("[Simulation Matrix] Plan exposes all software domains and external gates: PASSED")

    selected = run_matrix(execute=False, domain_ids=("SIM-001",))
    assert [item["domain_id"] for item in selected["software_domains"]] == ["SIM-001"]

    executed = run_matrix(execute=True, root=Path(__file__).resolve().parent, command_runner=successful_runner)
    assert executed["execution_mode"] == "EXECUTED"
    assert executed["software_simulation_passed"] is True
    assert all(item["status"] == "PASSED" for item in executed["software_domains"])
    print("[Simulation Matrix] Executed report requires every selected fixture to pass: PASSED")
    print("SOFTWARE_SIMULATION_MATRIX_TESTS_PASSED")


if __name__ == "__main__":
    run()
