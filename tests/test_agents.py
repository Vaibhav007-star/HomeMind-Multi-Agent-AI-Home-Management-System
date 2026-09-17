"""Unit and integration tests for HomeMind Five Agent Architecture (Phase 2)."""

import pytest
from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import (
    GlobalHomeState,
    DevicePowerState,
    DoorState,
    LockState
)
from backend.agents import (
    AgentType,
    AgentStatusEnum,
    ActionPriority,
    EnergyAgent,
    ComfortAgent,
    SecurityAgent,
    ResourceAgent,
    HomeManagerAgent
)


def test_energy_agent_detects_waste():
    """Verify EnergyAgent identifies appliances running in vacant rooms."""
    sim = HomeSimulator()
    # Turn ON Living Room TV and AC in Living Room, but ensure Living Room is unoccupied
    sim.set_device_power("tv_living", DevicePowerState.ON)
    sim.set_device_power("ac_living", DevicePowerState.ON)
    sim.set_occupancy("living_room", False)

    snapshot = sim.get_snapshot()
    agent = EnergyAgent()
    result = agent.evaluate(snapshot)

    assert result.agent_type == AgentType.ENERGY
    # Check that recommendations target tv_living and ac_living
    targets = [rec.target_id for rec in result.recommendations]
    assert "tv_living" in targets
    assert "ac_living" in targets

    # Check that explainable evidence is populated
    tv_rec = next(r for r in result.recommendations if r.target_id == "tv_living")
    assert any("unoccupied" in ev.lower() for ev in tv_rec.explainable_evidence)


def test_comfort_agent_manages_climate():
    """Verify ComfortAgent recommends climate adjustments when occupied room is hot."""
    sim = HomeSimulator()
    # Bedroom is occupied and warm (28°C), AC is OFF
    sim.set_occupancy("bedroom", True)
    sim.rooms["bedroom"].temperature_celsius = 28.0
    sim.set_device_power("ac_bedroom", DevicePowerState.OFF)

    snapshot = sim.get_snapshot()
    agent = ComfortAgent()
    result = agent.evaluate(snapshot)

    assert result.agent_type == AgentType.COMFORT
    targets = [rec.target_id for rec in result.recommendations]
    assert "ac_bedroom" in targets
    ac_rec = next(r for r in result.recommendations if r.target_id == "ac_bedroom")
    assert ac_rec.action == "TURN_ON"
    assert ac_rec.parameters.get("target_temp_celsius") == 24.0


def test_security_agent_flags_away_breaches():
    """Verify SecurityAgent generates alerts for door opening and motion during AWAY mode."""
    sim = HomeSimulator()
    sim.set_global_home_state(GlobalHomeState.AWAY)
    sim.set_door_state(True)  # Door OPEN in AWAY mode

    snapshot = sim.get_snapshot()
    agent = SecurityAgent()
    result = agent.evaluate(snapshot)

    assert result.agent_type == AgentType.SECURITY
    assert len(result.alerts) > 0
    assert any("Front Door" in a.title for a in result.alerts)
    assert any(a.severity == "CRITICAL" for a in result.alerts)


def test_resource_agent_water_and_supplies():
    """Verify ResourceAgent flags water levels and grocery restocking needs."""
    sim = HomeSimulator()
    # Lower water tank to 18% (below 25% threshold)
    sim.env.current_water_liters = 180.0

    snapshot = sim.get_snapshot()
    agent = ResourceAgent()
    result = agent.evaluate(snapshot)

    assert result.agent_type == AgentType.RESOURCE
    # Should propose turning on water pump
    pump_recs = [r for r in result.recommendations if r.target_id == "water_pump"]
    assert len(pump_recs) > 0
    assert pump_recs[0].action == "TURN_ON"

    # Grocery check
    restock_recs = [r for r in result.recommendations if r.target_id == "grocery_list"]
    assert len(restock_recs) > 0


def test_home_manager_delegation_and_conflict_resolution():
    """Verify HomeManager coordinates all sub-agents and resolves conflicts logically."""
    sim = HomeSimulator()
    # Scenario where Bedroom is occupied:
    # Bedroom temp is 27°C, AC is OFF.
    # Comfort Agent wants AC ON for resident comfort.
    # Energy Agent would want AC OFF if unoccupied, but room is occupied.
    sim.set_occupancy("bedroom", True)
    sim.rooms["bedroom"].temperature_celsius = 27.0
    sim.set_device_power("ac_bedroom", DevicePowerState.OFF)

    # Kitchen is vacant, but light is left ON -> Energy Agent wants light OFF
    sim.set_occupancy("kitchen", False)
    sim.set_device_power("light_kitchen", DevicePowerState.ON)

    snapshot = sim.get_snapshot()
    manager = HomeManagerAgent()
    decision = manager.coordinate_cycle(snapshot)

    assert decision.home_state == "HOME"
    assert len(decision.approved_actions) > 0

    approved_targets = [a.target_id for a in decision.approved_actions]
    assert "ac_bedroom" in approved_targets  # Comfort recommendation approved for occupied room
    assert "light_kitchen" in approved_targets  # Energy recommendation approved for empty room


def test_cross_agent_water_leak_correlation():
    """Verify Section 3 Example 2: HomeManager combines Resource + Security findings to identify water leak."""
    sim = HomeSimulator()
    sim.trigger_scenario_water_leak()  # Sets AWAY, leak 4.2 LPM, all rooms vacant

    snapshot = sim.get_snapshot()
    manager = HomeManagerAgent()
    result = manager.evaluate(snapshot)

    # HomeManager should generate cross-agent correlated alert
    correlated_alerts = [a for a in result.alerts if "Possible Water Leak" in a.title]
    assert len(correlated_alerts) > 0
    leak_alert = correlated_alerts[0]
    assert leak_alert.severity == "CRITICAL"
    assert any("Resource Agent" in ev for ev in leak_alert.evidence)
    assert any("Security Agent" in ev for ev in leak_alert.evidence)

