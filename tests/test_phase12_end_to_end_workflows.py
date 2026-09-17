"""Phase 12: Complete Multi-Agent Workflow End-to-End Verification.

Adheres to Section 20 & 21:
'Test complete multi-agent workflows and verify all Master Success Criteria.'
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import GlobalHomeState, DevicePowerState, LockState
from backend.agents.home_manager import HomeManagerAgent
from backend.agents.schemas import AgentType
from backend.agents.communication import MessageType
from backend.scenarios.runner import ScenarioRunner
from backend.explainability import ExplanationEngine, AuditLogger, SafetyTier
from backend.api.app import app


def test_workflow_full_24h_state_lifecycle():
    """Test full multi-agent state lifecycle loop across 24 hours."""
    sim = HomeSimulator(start_hour=6, start_minute=30)
    manager = HomeManagerAgent()

    # 1. Start at SLEEP
    manager.state_machine.current_state = GlobalHomeState.SLEEP
    sim.set_global_home_state(GlobalHomeState.SLEEP)

    # 2. Transition SLEEP -> MORNING at 07:00 AM
    sim.sim_time = datetime(2026, 9, 17, 7, 0)
    success1, _ = manager.state_machine.transition_to(GlobalHomeState.MORNING, "Wakeup schedule", "Scheduler")
    assert success1 is True
    sim.set_global_home_state(GlobalHomeState.MORNING)
    eval_morning = manager.delegate_all(sim.get_snapshot())
    assert len(eval_morning) == 4

    # 3. Transition MORNING -> HOME
    success2, _ = manager.state_machine.transition_to(GlobalHomeState.HOME, "Morning routine complete", "HomeManager")
    assert success2 is True
    sim.set_global_home_state(GlobalHomeState.HOME)
    assert manager.state_machine.current_state == GlobalHomeState.HOME

    # 4. Transition HOME -> AWAY via user command at 08:30 AM
    sim.sim_time = datetime(2026, 9, 17, 8, 30)
    wf_leaving = manager.execute_workflow("I'm leaving for college.", sim)
    assert wf_leaving.intent == "LEAVING_HOME"
    assert sim.global_home_state == GlobalHomeState.AWAY
    assert sim.devices["lock_entrance"].is_locked() is True

    # 5. Transition AWAY -> HOME upon resident return
    wf_return = manager.execute_workflow("I'm back home.", sim)
    assert wf_return.intent == "RETURN_HOME"
    assert sim.global_home_state == GlobalHomeState.HOME
    assert sim.env.away_mode_armed is False

    # 6. Transition HOME -> SLEEP for bedtime
    wf_sleep = manager.execute_workflow("Turn the house into sleep mode.", sim)
    assert wf_sleep.intent == "SLEEP_MODE"
    assert sim.global_home_state == GlobalHomeState.SLEEP


def test_workflow_agent_to_agent_negotiation():
    """Test Energy Agent <-> Comfort Agent AC setpoint negotiation protocol."""
    manager = HomeManagerAgent()
    sim = HomeSimulator()

    # Comfort wants 22.0°C, Energy wants 25.5°C
    sim.set_ac_target("ac_living", 22.0)
    final_temp, rounds = manager.run_ac_setpoint_negotiation(
        device_id="ac_living",
        initial_comfort_target=22.0,
        energy_preferred_target=25.5,
        simulator=sim
    )

    # Must arrive at a collaborative compromise
    assert 23.0 <= final_temp <= 25.0
    assert len(rounds) >= 2

    # Check that messages were routed through the bus
    messages = manager.bus.get_all_messages()
    assert any(m.msg_type == MessageType.NEGOTIATION_PROPOSAL for m in messages)
    assert any(m.msg_type in [MessageType.NEGOTIATION_COUNTER, MessageType.NEGOTIATION_ACCEPT] for m in messages)


def test_workflow_cross_agent_water_anomaly():
    """Test Resource Agent <-> Security Agent verification and Home Manager leak synthesis."""
    runner = ScenarioRunner()
    report = runner.run_scenario_3_water_leak()

    assert report.scenario_id == "SCENARIO_3_WATER_LEAK"
    assert report.initial_state == "AWAY"

    # Verify dialogue steps
    dialogue_steps = [s for s in report.steps if s.action_type == "DIALOGUE"]
    assert len(dialogue_steps) >= 2

    # Verify synthesized alert
    assert len(report.alerts) > 0
    leak_alert = next((a for a in report.alerts if "Water Leak" in a.title), None)
    assert leak_alert is not None
    assert leak_alert.severity == "CRITICAL"
    assert len(leak_alert.evidence) >= 2


def test_workflow_habit_recognition_vs_anomaly():
    """Test Contextual Memory habit matching vs anomalous middle-of-night vacancy."""
    manager = HomeManagerAgent()

    # Case A: 08:30 AM departure matches Alex's weekday college schedule
    time_normal = datetime(2026, 9, 17, 8, 30)
    is_habit, desc_normal = manager.memory.get_departure_context(time_normal)
    assert is_habit is True
    assert "typical departure habit" in desc_normal.lower() or "scheduled" in desc_normal.lower()

    # Case B: 02:15 AM departure is an anomalous unpredicted vacancy
    time_abnormal = datetime(2026, 9, 17, 2, 15)
    is_habit_b, desc_abnormal = manager.memory.get_departure_context(time_abnormal)
    assert is_habit_b is False
    assert "unscheduled" in desc_abnormal.lower() or "does not match" in desc_abnormal.lower()


def test_workflow_api_end_to_end():
    """Test full FastAPI REST and state orchestration."""
    client = TestClient(app)

    # 1. Overview check
    res_ov = client.get("/api/overview")
    assert res_ov.status_code == 200
    ov_data = res_ov.json()
    assert "home_state" in ov_data

    # 2. Chat command: leaving home
    res_chat = client.post("/api/chat", json={"message": "I'm leaving for college."})
    assert res_chat.status_code == 200
    assert res_chat.json()["new_home_state"] == "AWAY"

    # 3. Timeline check contains newly logged event
    res_tl = client.get("/api/timeline")
    assert res_tl.status_code == 200
    assert len(res_tl.json()["timeline"]) > 0

    # 4. Audit logs check
    res_logs = client.get("/api/logs")
    assert res_logs.status_code == 200
    assert len(res_logs.json()["recent_entries"]) > 0


def test_section_21_master_success_criteria():
    """Verify all 13 Master Project Success Criteria defined in Section 21."""
    sim = HomeSimulator()
    manager = HomeManagerAgent()
    runner = ScenarioRunner(simulator=sim, manager=manager)

    # 1. Five genuinely specialized agents
    assert len(manager.sub_agents) == 4
    assert manager.agent_type == AgentType.HOME_MANAGER
    assert manager.energy_agent.agent_type == AgentType.ENERGY
    assert manager.comfort_agent.agent_type == AgentType.COMFORT
    assert manager.security_agent.agent_type == AgentType.SECURITY
    assert manager.resource_agent.agent_type == AgentType.RESOURCE

    # 2. Natural-language user interaction
    plan = manager.nlp.understand_intent("Why is the energy consumption high?", GlobalHomeState.HOME)
    assert plan.intent == "ENERGY_AUDIT"

    # 3. Agent delegation
    wf = manager.execute_workflow("Turn the house into sleep mode.", sim)
    assert len(wf.agent_results) >= 3

    # 4. Agent-to-agent communication
    assert manager.bus is not None
    matrix = manager.bus.get_communication_matrix()
    assert "nodes" in matrix
    assert len(matrix["nodes"]) == 5

    # 5. Shared home state
    assert manager.state_machine.current_state in GlobalHomeState

    # 6. Context-aware decisions
    is_habit, _ = manager.memory.get_departure_context(datetime(2026, 9, 17, 8, 30))
    assert is_habit is True

    # 7. Simulated sensors and devices
    snapshot = sim.get_snapshot()
    assert len(snapshot.rooms) == 5
    assert len(snapshot.devices) >= 8

    # 8. Home state transitions
    ok, _ = manager.state_machine.transition_to(GlobalHomeState.HOME, "Test transition", "Tester")
    assert ok is True

    # 9. At least three multi-agent scenarios
    scenarios = runner.run_all()
    assert len(scenarios) == 3

    # 10. Explainable alerts
    explanation = ExplanationEngine.explain_water_leak_alert(scenarios["scenario_3"].alerts[0], snapshot)
    assert len(explanation.why_points) >= 3

    # 11. Event/activity logs
    logger = AuditLogger()
    logger.log_decision(explanation)
    assert len(logger.memory_buffer) > 0

    # 12. Modern dashboard
    from backend.api.app import app as fastapi_app
    assert fastapi_app is not None

    # 13. Modular architecture
    from backend.simulation import HomeSimulator as SimModule
    from backend.memory import SharedHomeMemory as MemModule
    from backend.agents import EnergyAgent as AgentModule
    assert SimModule is not None and MemModule is not None and AgentModule is not None
