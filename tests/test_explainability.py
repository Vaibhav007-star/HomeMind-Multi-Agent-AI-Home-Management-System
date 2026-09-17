"""Unit and integration tests for Explainable Decisions & Logging (Phase 10)."""

import pytest
import json
import csv
from pathlib import Path

from backend.explainability.models import DecisionExplanation, SafetyTier
from backend.explainability.engine import ExplanationEngine
from backend.explainability.logger import AuditLogger
from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import GlobalHomeState
from backend.agents.schemas import AgentType, AgentAlert
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture
def sim():
    s = HomeSimulator()
    s.set_global_home_state(GlobalHomeState.AWAY)
    for r in s.rooms.values():
        r.occupied = False
    return s


def test_explain_water_leak_section_13(sim):
    """Verify water leak explanation matches Section 13 specification."""
    alert = AgentAlert(
        agent_type=AgentType.HOME_MANAGER,
        title="Possible water leakage detected.",
        severity="CRITICAL",
        description="High flow detected while residence is vacant.",
        evidence=["Outflow 4.2 L/min", "Zero occupancy"]
    )
    snapshot = sim.get_snapshot()

    exp = ExplanationEngine.explain_water_leak_alert(alert, snapshot, leak_rate_lpm=4.2)

    assert exp.decision_type == "ALERT"
    assert exp.safety_tier == SafetyTier.REQUIRES_CONFIRMATION
    assert len(exp.why_points) == 4

    # Check the 4 canonical Section 13 bullet points
    why_text = " ".join(exp.why_points).lower()
    assert "away mode" in why_text
    assert "increased significantly" in why_text
    assert "no resident activity detected" in why_text
    assert "differs from normal" in why_text


def test_explain_energy_shedding():
    """Verify energy load shedding explanation."""
    exp = ExplanationEngine.explain_energy_shedding(
        device_name="Living Room TV",
        room_name="Living Room",
        watts_saved=110.0,
        reason="Vacant room load shedding",
        is_peak=True
    )

    assert exp.decision_type == "ACTION"
    assert exp.origin_agent == AgentType.ENERGY
    assert exp.safety_tier == SafetyTier.SAFE_AUTONOMOUS
    assert any("unoccupied" in p.lower() for p in exp.why_points)
    assert any("peak" in p.lower() for p in exp.why_points)


def test_explain_conflict_resolution():
    """Verify multi-agent arbitration explanation."""
    exp = ExplanationEngine.explain_conflict_resolution(
        target_device="ac_living",
        chosen_agent=AgentType.COMFORT,
        chosen_action="SET_TEMP 24C",
        overruled_agent=AgentType.ENERGY,
        overruled_action="TURN_OFF",
        reason="Living room actively occupied by resident."
    )

    assert exp.decision_type == "CONFLICT_RESOLUTION"
    assert exp.origin_agent == AgentType.HOME_MANAGER
    assert len(exp.participating_agents) == 3


def test_audit_logger_disk_and_memory(tmp_path):
    """Verify logger writes correctly to JSONL and CSV."""
    logger = AuditLogger(log_dir=tmp_path)

    exp = DecisionExplanation(
        title="Test Security Lock",
        decision_type="ACTION",
        origin_agent=AgentType.SECURITY,
        summary="Entrance locked for nighttime safety.",
        why_points=["Sleep mode active", "Entrance unlocked"]
    )

    logger.log_decision(exp)

    # Check memory buffer
    recent = logger.get_recent(limit=10)
    assert len(recent) == 1
    assert recent[0].title == "Test Security Lock"

    # Check JSONL
    assert logger.jsonl_path.exists()
    with open(logger.jsonl_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["title"] == "Test Security Lock"

    # Check CSV
    assert logger.csv_path.exists()
    with open(logger.csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 2  # Header + 1 row
        assert reader[1][4] == "Test Security Lock"


def test_api_explanations_and_logs():
    """Verify /api/explanations and /api/logs endpoints."""
    client = TestClient(app)

    # Trigger scenario 3 to populate water leak explanation
    res_scen = client.post("/api/scenario/3")
    assert res_scen.status_code == 200

    # Test /api/explanations
    res_exp = client.get("/api/explanations")
    assert res_exp.status_code == 200
    explanations = res_exp.json()["explanations"]
    assert len(explanations) > 0

    leak_exp = next((e for e in explanations if "Leak" in e["title"] or "leak" in e["title"]), None)
    assert leak_exp is not None
    assert len(leak_exp["why_points"]) >= 3

    # Test /api/logs
    res_logs = client.get("/api/logs")
    assert res_logs.status_code == 200
    assert "log_files" in res_logs.json()
    assert "recent_entries" in res_logs.json()

    # Test action confirmation
    confirm_res = client.post(f"/api/explanations/{leak_exp['explanation_id']}/confirm")
    assert confirm_res.status_code == 200
    assert confirm_res.json()["explanation"]["user_confirmed"] is True

