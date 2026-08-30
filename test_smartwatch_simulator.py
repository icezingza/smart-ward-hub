from datetime import datetime, timezone

from smartwatch_simulator import _local_telemetry_sender, build_scenario, run_scenario


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)


def run() -> None:
    normal = build_scenario("normal", sample_count=3, start_time=NOW)
    assert [event.packet.sequence for event in normal if event.packet] == [1, 2, 3]
    assert all(event.packet and event.packet.device_id == "smartwatch-sim-001" for event in normal)
    dry_run = run_scenario(normal)
    assert dry_run["network_mode"] == "dry_run"
    assert dry_run["passed"] is True
    assert all(row["actual_status"] == "NOT_SENT" for row in dry_run["events"])
    print("[Smart Watch simulator] Deterministic synthetic dry-run: PASSED")

    accepted_sequences: list[int] = []

    def sender(packet):
        if packet.sequence in accepted_sequences:
            return 409
        accepted_sequences.append(packet.sequence)
        return 200

    replay = run_scenario(build_scenario("replay", sample_count=2, start_time=NOW), sender)
    assert replay["passed"] is True
    assert [row["actual_status"] for row in replay["events"]] == [200, 200, 409]
    print("[Smart Watch simulator] Replay rejection expectation: PASSED")

    ordered_sequences: list[int] = []

    def ordered_sender(packet):
        if ordered_sequences and packet.sequence <= ordered_sequences[-1]:
            return 409
        ordered_sequences.append(packet.sequence)
        return 200

    out_of_order = run_scenario(build_scenario("out_of_order", sample_count=2, start_time=NOW), ordered_sender)
    assert out_of_order["passed"] is True
    assert [row["actual_status"] for row in out_of_order["events"]] == [200, 200, 409]

    reconnect = run_scenario(build_scenario("offline_reconnect", sample_count=3, start_time=NOW))
    assert reconnect["passed"] is True
    assert [row["kind"] for row in reconnect["events"]] == ["telemetry", "disconnect", "reconnect", "telemetry", "telemetry"]
    print("[Smart Watch simulator] Out-of-order and offline/reconnect scenarios: PASSED")

    for unsafe_url in ("https://127.0.0.1:8000", "http://hub.example.test:8000"):
        try:
            _local_telemetry_sender(unsafe_url, "test-token")
        except ValueError as error:
            assert "loopback" in str(error)
        else:
            raise AssertionError("simulator must reject non-loopback or HTTPS endpoints")
    print("[Smart Watch simulator] Network send remains loopback-only: PASSED")
    print("SMARTWATCH_SIMULATOR_TESTS_PASSED")


if __name__ == "__main__":
    run()
