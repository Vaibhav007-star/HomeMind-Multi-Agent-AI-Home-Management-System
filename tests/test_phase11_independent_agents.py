"""Phase 11: Independent Agent Unit Testing Suite.

Adheres to Section 17 & 20:
'Keep these layers modular so individual agents can be tested independently.'
Tests each of the 5 specialized agents in complete isolation.
"""

import pytest
from datetime import datetime

from backend.agents.schemas import AgentType, AgentStatusEnum, ActionPriority
from backend.agents.energy_agent import EnergyAgent
from backend.agents.comfort_agent import ComfortAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.resource_agent import ResourceAgent
from backend.agents.home_manager import HomeManagerAgent
from backend.agents.orchestration import DelegationTask
from backend.simulation.models import (
    HomeStateSnapshot,
    GlobalHomeState,
    RoomEnvironment,
    DeviceState,
    DeviceType,
    DevicePowerState,
    EnergySystemState,
    WaterSystemState,
    SecuritySystemState,
    DoorState,
    LockState
)
from backend.simulation.simulator import HomeSimulator


# ==========================================
# 1. Independent Energy Agent Tests
# ==========================================
def test_energy_agent_isolated_evaluation():
    """Test Energy Agent independently audits loads and flags unoccupied room waste."""
    agent = EnergyAgent()
    assert agent.agent_type == AgentType.ENERGY

    # Create synthetic snapshot: TV and lights running in an unoccupied living room
    snapshot = HomeStateSnapshot(
        timestamp=datetime(2026, 9, 17, 14, 0),
        simulation_time_str="02:00 PM",
        global_home_state=GlobalHomeState.HOME,
        rooms={
            "living_room": RoomEnvironment(room_id="living_room", room_name="Living Room", occupied=False, motion_detected=False)
        },
        devices={
            "tv_living": DeviceState(id="tv_living", name="Living TV", room_id="living_room", device_type=DeviceType.TV, power_state=DevicePowerState.ON, power_draw_watts=110.0),
            "light_living": DeviceState(id="light_living", name="Living Light", room_id="living_room", device_type=DeviceType.LIGHT, power_state=DevicePowerState.ON, power_draw_watts=20.0)
        },
        energy_system=EnergySystemState(instant_power_watts=130.0)
    )

    eval_result = agent.evaluate(snapshot)

    assert eval_result.agent_type == AgentType.ENERGY
    assert len(eval_result.recommendations) >= 2
    rec_targets = [r.target_id for r in eval_result.recommendations]
    assert "tv_living" in rec_targets
    assert "light_living" in rec_targets
    assert all(r.action == "TURN_OFF" for r in eval_result.recommendations)


def test_energy_agent_isolated_task_execution():
    """Test Energy Agent independently handles delegated task."""
    agent = EnergyAgent()
    sim = HomeSimulator()
    sim.devices["tv_living"].turn_on()

    task = DelegationTask(
        recipient=AgentType.ENERGY,
        command="DEACTIVATE_UNNECESSARY_LOADS",
        instruction="Shut off discretionary appliances.",
        parameters={"all_vacant": True}
    )

    result = agent.handle_task(task, sim)
    assert result.success is True
    assert sim.devices["tv_living"].power_state == DevicePowerState.OFF


# ==========================================
# 2. Independent Comfort Agent Tests
# ==========================================
def test_comfort_agent_isolated_climate_bounds():
    """Test Comfort Agent independently enforces 22.0°C - 25.5°C thermal bounds."""
    agent = ComfortAgent()
    assert agent.agent_type == AgentType.COMFORT

    # Bedroom is hot (28.5°C) and occupied
    snapshot = HomeStateSnapshot(
        timestamp=datetime(2026, 9, 17, 15, 0),
        simulation_time_str="03:00 PM",
        global_home_state=GlobalHomeState.HOME,
        rooms={
            "bedroom": RoomEnvironment(room_id="bedroom", room_name="Bedroom", temperature_celsius=28.5, occupied=True)
        },
        devices={
            "ac_bedroom": DeviceState(id="ac_bedroom", name="Bedroom AC", room_id="bedroom", device_type=DeviceType.AC, power_state=DevicePowerState.OFF)
        }
    )

    eval_result = agent.evaluate(snapshot)
    assert len(eval_result.recommendations) > 0
    ac_rec = next((r for r in eval_result.recommendations if r.target_id == "ac_bedroom"), None)
    assert ac_rec is not None
    assert ac_rec.action == "TURN_ON"


def test_comfort_agent_isolated_task_execution():
    """Test Comfort Agent independently handles sleep climate delegation."""
    agent = ComfortAgent()
    sim = HomeSimulator()

    task = DelegationTask(
        recipient=AgentType.COMFORT,
        command="PREPARE_SLEEP_COMFORT",
        instruction="Configure bedroom for sleep."
    )

    result = agent.handle_task(task, sim)
    assert result.success is True
    assert sim.devices["ac_bedroom"].power_state == DevicePowerState.ON


# ==========================================
# 3. Independent Security Agent Tests
# ==========================================
def test_security_agent_isolated_perimeter_breach():
    """Test Security Agent independently detects door open in AWAY mode."""
    agent = SecurityAgent()
    assert agent.agent_type == AgentType.SECURITY

    snapshot = HomeStateSnapshot(
        timestamp=datetime(2026, 9, 17, 12, 0),
        simulation_time_str="12:00 PM",
        global_home_state=GlobalHomeState.AWAY,
        security_system=SecuritySystemState(
            entrance_door_state=DoorState.OPEN,
            entrance_lock_state=LockState.UNLOCKED,
            away_mode_armed=True
        )
    )

    eval_result = agent.evaluate(snapshot)
    assert len(eval_result.alerts) > 0
    breach_alert = next((a for a in eval_result.alerts if a.severity == "CRITICAL"), None)
    assert breach_alert is not None
    assert "Perimeter Breach" in breach_alert.title


def test_security_agent_isolated_task_execution():
    """Test Security Agent independently handles arming away mode."""
    agent = SecurityAgent()
    sim = HomeSimulator()
    sim.set_lock_state(False)

    task = DelegationTask(
        recipient=AgentType.SECURITY,
        command="ARM_AWAY_MONITORING",
        instruction="Lock door and arm sensors."
    )

    result = agent.handle_task(task, sim)
    assert result.success is True
    assert sim.devices["lock_entrance"].is_locked() is True
    assert sim.env.away_mode_armed is True


# ==========================================
# 4. Independent Resource Agent Tests
# ==========================================
def test_resource_agent_isolated_tank_audit():
    """Test Resource Agent independently audits low water tank levels."""
    agent = ResourceAgent()
    assert agent.agent_type == AgentType.RESOURCE

    # Tank at 18% (critical low)
    snapshot = HomeStateSnapshot(
        timestamp=datetime(2026, 9, 17, 10, 0),
        simulation_time_str="10:00 AM",
        global_home_state=GlobalHomeState.HOME,
        water_system=WaterSystemState(current_water_liters=180.0, water_level_percent=18.0)
    )

    eval_result = agent.evaluate(snapshot)
    assert len(eval_result.recommendations) > 0
    pump_rec = next((r for r in eval_result.recommendations if r.target_id == "water_pump"), None)
    assert pump_rec is not None
    assert pump_rec.action == "TURN_ON"


def test_resource_agent_isolated_inventory_audit():
    """Test Resource Agent independently audits groceries and consumables."""
    agent = ResourceAgent()
    sim = HomeSimulator()

    task = DelegationTask(
        recipient=AgentType.RESOURCE,
        command="INVENTORY_AUDIT",
        instruction="Check restock levels."
    )

    result = agent.handle_task(task, sim)
    assert result.success is True
    assert "restock_items" in result.data
    assert len(result.data["restock_items"]) > 0


# ==========================================
# 5. Independent Home Manager Agent Tests
# ==========================================
def test_home_manager_isolated_intent_and_arbitration():
    """Test Home Manager independently resolves conflicts between competing proposals."""
    manager = HomeManagerAgent()
    assert manager.agent_type == AgentType.HOME_MANAGER

    from backend.agents.schemas import AgentActionProposal

    # Scenario: Energy wants AC turned OFF (save power), Comfort wants AC turned ON (comfort)
    proposal_energy = AgentActionProposal(
        agent_type=AgentType.ENERGY,
        target_type="device",
        target_id="ac_living",
        action="TURN_OFF",
        priority=ActionPriority.MEDIUM,
        reason="Save power"
    )
    proposal_comfort = AgentActionProposal(
        agent_type=AgentType.COMFORT,
        target_type="device",
        target_id="ac_living",
        action="TURN_ON",
        priority=ActionPriority.MEDIUM,
        reason="Restore comfort"
    )

    # In an OCCUPIED living room during HOME mode: Comfort must prevail
    snapshot_occupied = HomeStateSnapshot(
        global_home_state=GlobalHomeState.HOME,
        rooms={"living_room": RoomEnvironment(room_id="living_room", room_name="Living Room", occupied=True)},
        devices={"ac_living": DeviceState(id="ac_living", name="Living AC", room_id="living_room", device_type=DeviceType.AC)}
    )
    resolved, conflicts = manager.resolve_conflicts([proposal_energy, proposal_comfort], snapshot_occupied)
    assert len(resolved) == 1
    assert resolved[0].agent_type == AgentType.COMFORT

    # In an UNOCCUPIED room: Energy must prevail
    snapshot_unoccupied = HomeStateSnapshot(
        global_home_state=GlobalHomeState.HOME,
        rooms={"living_room": RoomEnvironment(room_id="living_room", room_name="Living Room", occupied=False)},
        devices={"ac_living": DeviceState(id="ac_living", name="Living AC", room_id="living_room", device_type=DeviceType.AC)}
    )
    resolved2, conflicts2 = manager.resolve_conflicts([proposal_energy, proposal_comfort], snapshot_unoccupied)
    assert len(resolved2) == 1
    assert resolved2[0].agent_type == AgentType.ENERGY
