"""Pure prototype telemetry triage shared by the Hub and synthetic simulations."""

from __future__ import annotations

from statistics import pstdev
from typing import Any


def evaluate_telemetry_triage(samples: list[dict[str, Any]], risk_level: str) -> dict[str, str] | None:
    """Return a non-diagnostic prototype signal for an already-authorized device."""
    recent = samples[-30:]
    for index, sample in enumerate(recent):
        if sample["g_force"] <= 2.5:
            continue
        subsequent = recent[index + 1 : index + 6]
        if len(subsequent) < 5:
            continue
        g_forces = [item["g_force"] for item in subsequent]
        if pstdev(g_forces) < 0.15 and abs(sum(g_forces) / len(g_forces) - 1.0) < 0.25:
            return {"alert_level": "RED", "alert_type": "FALL"}

    latest = recent[-1]
    physiological_score = 0.0
    if latest.get("spo2") is not None:
        if latest["spo2"] < 90:
            physiological_score += 100
        elif latest["spo2"] < 95:
            physiological_score += 40
    if latest.get("heart_rate") is not None and (latest["heart_rate"] < 50 or latest["heart_rate"] > 120):
        physiological_score += 60
    risk_score = {"High": 100.0, "Medium": 50.0, "Low": 10.0}.get(risk_level, 10.0)
    triage_score = (0.618 * min(100.0, physiological_score)) + (0.382 * risk_score)
    if triage_score >= 50.0 or (latest.get("spo2") is not None and latest["spo2"] < 90):
        return {"alert_level": "RED", "alert_type": "VITAL_ANOMALY"}
    return None
