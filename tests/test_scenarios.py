"""Unit and integration tests for HomeMind Demonstration Scenarios (Phase 7)."""

import pytest
from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import GlobalHomeState, DevicePowerState
from backend.agents.home_manager import HomeManagerAgent
from backend.scenarios.runner import ScenarioRunner


def test_scenario_1_morning_routine():
    """Verify Scenario 1 (Morning Routine) runs and executes multi-agent actions."""
    sim = HomeSimulator()
    manager = HomeManagerAgent()
    runner = ScenarioRunner(simulator=sim, manager=manager)

    report = runner.run_scenario_1_morning()

    assert report.scenario_id == "SCENARIO_1_MORNING"
    assert report.initial_state == "SLEEP"
    assert report.final_state == "HOME"
    assert len(report.steps) >= 6

    # Verify device state mutations
    assert sim.devices["light_kitchen"].power_state == DevicePowerState.ON
    assert sim.devices["light_living"].power_state == DevicePowerState.ON
    assert sim.devices["ac_bedroom"].power_state == DevicePowerState.OFF
    assert sim.global_home_state == GlobalHomeState.HOME

    # Verify explainability and agent summaries
    assert "Comfort Agent" in report.agent_summaries
    assert "Energy Agent" in report.agent_summaries
    assert "Resource Agent" in report.agent_summaries
    assert "Security Agent" in report.agent_summaries
    assert "Home Manager" in report.agent_summaries
    assert len(report.explainability_summary) > 20


def test_scenario_2_leaving_home():
    """Verify Scenario 2 (Leaving Home) executes natural-language delegation to AWAY state."""
    sim = HomeSimulator()
    manager = HomeManagerAgent()
    runner = ScenarioRunner(simulator=sim, manager=manager)

    report = runner.run_scenario_2_leaving()

    assert report.scenario_id == "SCENARIO_2_LEAVING"
    assert report.initial_state == "HOME"
    assert report.final_state == "AWAY"
    assert len(report.steps) >= 5

    # Verify delegated shedding
    assert sim.devices["tv_living"].power_state == DevicePowerState.OFF
    assert sim.devices["light_kitchen"].power_state == DevicePowerState.OFF
    assert sim.devices["ac_living"].power_state == DevicePowerState.OFF
    assert sim.devices["lock_entrance"].is_locked() is True
    assert sim.env.away_mode_armed is True
    assert sim.global_home_state == GlobalHomeState.AWAY

    # Verify step evidence
    for step in report.steps:
        assert step.actor != ""
        assert step.description != ""
        assert len(step.evidence) > 0


def test_scenario_3_water_leak_detection():
    """Verify Scenario 3 (Abnormal Water Usage while AWAY) performs cross-agent verification."""
    sim = HomeSimulator()
    manager = HomeManagerAgent()
    runner = ScenarioRunner(simulator=sim, manager=manager)

    report = runner.run_scenario_3_water_leak()

    assert report.scenario_id == "SCENARIO_3_WATER_LEAK"
    assert report.initial_state == "AWAY"
    assert report.final_state == "AWAY"
    assert len(report.steps) >= 5

    # Verify inter-agent dialogue was recorded in steps
    dialogue_steps = [s for s in report.steps if s.action_type == "DIALOGUE"]
    assert len(dialogue_steps) >= 2

    # Verify alert synthesis
    assert len(report.alerts) > 0
    leak_alert = next((a for a in report.alerts if "Water Leak" in a.title), None)
    assert leak_alert is not None
    assert leak_alert.severity == "CRITICAL"
    assert len(leak_alert.evidence) >= 2

    # Explainability summary must highlight multi-agent synthesis
    assert "Resource Agent" in report.explainability_summary
    assert "Security Agent" in report.explainability_summary


def test_scenario_runner_run_all():
    """Verify runner.run_all executes all three scenarios smoothly."""
    runner = ScenarioRunner()
    results = runner.run_all()

    assert "scenario_1" in results
    assert "scenario_2" in results
    assert "scenario_3" in results

    assert results["scenario_1"].scenario_id == "SCENARIO_1_MORNING"
    assert results["scenario_2"].scenario_id == "SCENARIO_2_LEAVING"
    assert results["scenario_3"].scenario_id == "SCENARIO_3_WATER_LEAK"
