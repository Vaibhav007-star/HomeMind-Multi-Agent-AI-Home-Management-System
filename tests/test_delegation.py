"""Unit and integration tests for Home Manager Delegation & Orchestration (Phase 3)."""

import pytest
from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import (
    GlobalHomeState,
    DevicePowerState,
    LockState
)
from backend.agents import (
    HomeManagerAgent,
    AgentType
)


def test_leaving_home_delegation():
    """Verify Section 3 Example 3: Home Manager delegates 'leaving for college' to 4 agents."""
    sim = HomeSimulator()
    # Initial state: AC and TV in living room are ON
    sim.set_device_power("tv_living", DevicePowerState.ON)
    sim.set_device_power("ac_living", DevicePowerState.ON)
    sim.set_device_power("light_kitchen", DevicePowerState.ON)
    sim.set_lock_state(False)  # Smart lock currently unlocked

    manager = HomeManagerAgent()
    result = manager.execute_workflow("I'm leaving for college.", sim)

    # 1. Intent and Plan validation
    assert result.intent == "LEAVING_HOME"
    assert result.target_home_state == "AWAY"
    assert len(result.delegation_plan.tasks) == 4

    # 2. Verify all 4 agents received delegated tasks
    assert AgentType.ENERGY.value in result.agent_results
    assert AgentType.COMFORT.value in result.agent_results
    assert AgentType.SECURITY.value in result.agent_results
    assert AgentType.RESOURCE.value in result.agent_results

    # 3. Verify digital twin state actuations
    assert sim.global_home_state == GlobalHomeState.AWAY
    assert sim.env.entrance_lock_state == LockState.LOCKED
    assert sim.devices["tv_living"].power_state == DevicePowerState.OFF
    assert sim.devices["ac_living"].power_state == DevicePowerState.OFF
    assert sim.devices["light_kitchen"].power_state == DevicePowerState.OFF

    # 4. Verify structured timeline and explainable response
    assert len(result.timeline) >= 6
    assert "Home Manager Response" in result.final_response


def test_sleep_mode_delegation():
    """Verify user request 'Turn the house into sleep mode'."""
    sim = HomeSimulator()
    sim.set_device_power("light_living", DevicePowerState.ON)
    sim.set_lock_state(False)

    manager = HomeManagerAgent()
    result = manager.execute_workflow("Turn the house into sleep mode.", sim)

    assert result.intent == "SLEEP_MODE"
    assert sim.global_home_state == GlobalHomeState.SLEEP
    assert sim.env.entrance_lock_state == LockState.LOCKED

    # Comfort agent should have set bedroom AC
    ac_bed = sim.devices["ac_bedroom"]
    assert ac_bed.power_state == DevicePowerState.ON
    assert ac_bed.attributes.get("target_temp_celsius") == 23.5


def test_energy_audit_delegation():
    """Verify 'Why is energy consumption high?' delegates to Energy Agent."""
    sim = HomeSimulator()
    # Turn on high loads
    sim.set_device_power("ac_bedroom", DevicePowerState.ON)
    sim.set_device_power("tv_living", DevicePowerState.ON)

    manager = HomeManagerAgent()
    result = manager.execute_workflow("Why is the energy consumption high?", sim)

    assert result.intent == "ENERGY_AUDIT"
    assert AgentType.ENERGY.value in result.agent_results
    energy_res = result.agent_results[AgentType.ENERGY.value]
    assert energy_res.success is True
    assert "Total demand" in energy_res.report
    assert "top_consumers" in energy_res.data


def test_security_status_delegation():
    """Verify 'Is everything okay at home?' audits security & plumbing."""
    sim = HomeSimulator()
    manager = HomeManagerAgent()
    result = manager.execute_workflow("Is everything okay at home?", sim)

    assert result.intent == "SECURITY_STATUS"
    assert AgentType.SECURITY.value in result.agent_results
    assert AgentType.RESOURCE.value in result.agent_results
    assert "Security Audit" in result.agent_results[AgentType.SECURITY.value].report


def test_grocery_shopping_delegation():
    """Verify 'Do we need to buy anything?' queries Resource Agent inventory."""
    sim = HomeSimulator()
    manager = HomeManagerAgent()
    result = manager.execute_workflow("Do we need to buy anything?", sim)

    assert result.intent == "GROCERY_CHECK"
    assert AgentType.RESOURCE.value in result.agent_results
    res_report = result.agent_results[AgentType.RESOURCE.value].report
    assert "Inventory Audit" in res_report


def test_return_home_delegation():
    """Verify 'I'm back home' disarms away mode and prepares comfort."""
    sim = HomeSimulator()
    sim.set_global_home_state(GlobalHomeState.AWAY)
    sim.env.away_mode_armed = True

    manager = HomeManagerAgent()
    result = manager.execute_workflow("I'm home from university!", sim)

    assert result.intent == "RETURN_HOME"
    assert sim.global_home_state == GlobalHomeState.HOME
    assert sim.env.away_mode_armed is False

