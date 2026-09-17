"""Unit and integration tests for Agent-to-Agent Communication Layer (Phase 4)."""

import pytest
from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import DevicePowerState, GlobalHomeState
from backend.agents import (
    HomeManagerAgent,
    AgentType,
    MessageType,
    AgentMessage,
    AgentMessageBus
)


def test_message_bus_routing():
    """Verify basic message delivery and inbox management."""
    bus = AgentMessageBus()
    msg = AgentMessage(
        sender=AgentType.ENERGY,
        receiver=AgentType.COMFORT,
        msg_type=MessageType.INFORM,
        topic="POWER_ALERT",
        content="Current draw is high."
    )
    bus.send(msg)

    inbox = bus.get_inbox(AgentType.COMFORT)
    assert len(inbox) == 1
    assert inbox[0].topic == "POWER_ALERT"

    # Conversation history
    conv = bus.get_conversation(AgentType.ENERGY, AgentType.COMFORT)
    assert len(conv) == 1


def test_energy_comfort_negotiation_compromise():
    """Verify Section 3 Example 1: Energy Agent proposes AC setpoint increase, Comfort Agent accepts."""
    sim = HomeSimulator()
    sim.set_device_power("ac_bedroom", DevicePowerState.ON)
    sim.set_ac_target("ac_bedroom", 22.0)
    sim.rooms["bedroom"].temperature_celsius = 25.0

    manager = HomeManagerAgent()
    reply = manager.run_climate_energy_negotiation("ac_bedroom", proposed_setpoint=24.0, simulator=sim)

    assert reply is not None
    assert reply.msg_type == MessageType.NEGOTIATION_ACCEPT
    assert reply.sender == AgentType.COMFORT
    assert reply.receiver == AgentType.ENERGY

    # Verify AC setpoint was updated in digital twin
    assert sim.devices["ac_bedroom"].attributes["target_temp_celsius"] == 24.0

    # Verify conversation logged on bus
    conv = manager.bus.get_conversation(AgentType.ENERGY, AgentType.COMFORT)
    assert len(conv) >= 2
    assert any(m.msg_type == MessageType.NEGOTIATION_PROPOSAL for m in conv)
    assert any(m.msg_type == MessageType.NEGOTIATION_ACCEPT for m in conv)


def test_energy_comfort_negotiation_counter_proposal():
    """Verify Comfort Agent counters if Energy Agent proposes setpoint outside acceptable bounds."""
    sim = HomeSimulator()
    sim.set_device_power("ac_bedroom", DevicePowerState.ON)
    sim.set_ac_target("ac_bedroom", 22.0)
    sim.rooms["bedroom"].temperature_celsius = 25.0

    manager = HomeManagerAgent()
    # Energy proposes 27.0°C (exceeds preferred max 25.5°C)
    reply = manager.run_climate_energy_negotiation("ac_bedroom", proposed_setpoint=27.0, simulator=sim)

    assert reply is not None
    assert reply.msg_type == MessageType.NEGOTIATION_COUNTER
    # Counter-proposal should clamp to 25.5°C
    assert sim.devices["ac_bedroom"].attributes["target_temp_celsius"] == 25.5


def test_resource_security_cross_inquiry():
    """Verify Section 3 Example 2: Resource Agent queries Security Agent to confirm abnormal water usage."""
    sim = HomeSimulator()
    sim.trigger_scenario_water_leak()  # Sets AWAY, leak 4.2 LPM, all rooms vacant

    manager = HomeManagerAgent()
    reply = manager.run_water_security_verification(simulator=sim)

    assert reply is not None
    assert reply.msg_type == MessageType.RESPONSE
    assert reply.sender == AgentType.SECURITY
    assert reply.receiver == AgentType.RESOURCE
    assert reply.payload.get("is_unoccupied") is True

    # Check that Resource Agent also notified Home Manager
    conv_hm = manager.bus.get_conversation(AgentType.RESOURCE, AgentType.HOME_MANAGER)
    assert any(m.topic == "CORRELATED_LEAKAGE_CONFIRMED" for m in conv_hm)


def test_communication_matrix_section_11():
    """Verify Section 11 Communication View graph data structure."""
    sim = HomeSimulator()
    manager = HomeManagerAgent()

    # Execute workflow and peer dialogues
    manager.execute_workflow("I'm leaving for college.", sim)
    manager.run_climate_energy_negotiation("ac_living", proposed_setpoint=24.0, simulator=sim)
    sim.set_water_leak(True, leak_rate_lpm=3.8)
    manager.run_water_security_verification(simulator=sim)

    matrix = manager.get_communication_matrix()
    assert "nodes" in matrix
    assert "edges" in matrix
    assert len(matrix["nodes"]) == 5

    # Check that edges exist for key inter-agent links
    edge_pairs = [(e["source"], e["target"]) for e in matrix["edges"]]
    assert ("HOME_MANAGER", "ENERGY") in edge_pairs
    assert ("ENERGY", "HOME_MANAGER") in edge_pairs
    assert ("ENERGY", "COMFORT") in edge_pairs
    assert ("COMFORT", "ENERGY") in edge_pairs
    assert ("RESOURCE", "SECURITY") in edge_pairs
    assert ("SECURITY", "RESOURCE") in edge_pairs
