"""Interactive demonstration of Agent-to-Agent Communication Layer (Phase 4)."""

from backend.simulation import HomeSimulator, DevicePowerState
from backend.agents import HomeManagerAgent, AgentType


def print_banner(title: str):
    print("\n" + "=" * 72)
    print(f"   {title}")
    print("=" * 72)


def print_dialogue_message(msg):
    sender_name = msg.sender.value.replace("_", " ").title() + " Agent"
    receiver_name = msg.receiver.value.replace("_", " ").title() + " Agent"
    time_str = msg.timestamp.strftime("%H:%M:%S")
    print(f"\n  [{time_str}] {sender_name}  -->  {receiver_name}")
    print(f"  Type: [{msg.msg_type.value}] | Topic: {msg.topic}")
    print(f"  Content: \"{msg.content}\"")


def run_demo():
    print_banner("HomeMind — Phase 4: Agent-to-Agent Communication Layer Demo")
    sim = HomeSimulator(start_hour=14, start_minute=15)
    manager = HomeManagerAgent()

    # 1. Section 3 Example 1: Energy <-> Comfort Direct Negotiation
    print_banner("DIALOGUE 1: Section 3 Example 1 — Energy <-> Comfort Negotiation")
    print("Scenario: Living Room AC is running cold (21°C) during hot afternoon.")
    sim.set_device_power("ac_living", DevicePowerState.ON)
    sim.set_ac_target("ac_living", 21.0)
    sim.rooms["living_room"].temperature_celsius = 25.5

    reply1 = manager.run_climate_energy_negotiation("ac_living", proposed_setpoint=24.5, simulator=sim)
    
    # Retrieve dialogue
    conv1 = manager.bus.get_conversation(AgentType.ENERGY, AgentType.COMFORT)
    for msg in conv1:
        print_dialogue_message(msg)

    print(f"\n[Resulting Digital Twin State]: Living Room AC thermostat setpoint is now: {sim.devices['ac_living'].attributes['target_temp_celsius']}°C")

    # 2. Section 3 Example 2: Resource <-> Security Direct Cross-Inquiry
    print_banner("DIALOGUE 2: Section 3 Example 2 — Resource <-> Security Cross-Inquiry")
    print("Scenario: Unexpected water outflow detected while residence is marked AWAY.")
    sim.trigger_scenario_water_leak()  # Injects 4.2 L/min leak while unoccupied

    reply2 = manager.run_water_security_verification(simulator=sim)

    conv2 = manager.bus.get_conversation(AgentType.RESOURCE, AgentType.SECURITY)
    for msg in conv2:
        print_dialogue_message(msg)

    # Correlated alert sent to Home Manager
    conv_hm = manager.bus.get_conversation(AgentType.RESOURCE, AgentType.HOME_MANAGER)
    for msg in conv_hm:
        print_dialogue_message(msg)

    # 3. Section 11: Visual Communication Matrix View
    print_banner("SECTION 11: Visual Communication Matrix / Graph")
    matrix = manager.get_communication_matrix()

    print("\nVisual Active Channel Topology:")
    print("  +----------------+        negotiates        +----------------+")
    print("  |  Energy Agent  | <=====================> | Comfort Agent  |")
    print("  +----------------+                          +----------------+")
    print("          ^                                           ^         ")
    print("          | delegates                                 |         ")
    print("          v                                           v         ")
    print("  +------------------------------------------------------------+")
    print("  |                    Home Manager Agent                      |")
    print("  +------------------------------------------------------------+")
    print("          ^                                           ^         ")
    print("          | alerts                                    | alerts  ")
    print("          v                                           v         ")
    print("  +----------------+        cross-inquiry     +----------------+")
    print("  | Resource Agent | <=====================> | Security Agent |")
    print("  +----------------+                          +----------------+")

    print(f"\nTotal Inter-Agent Messages Routed: {matrix['total_messages']}")
    print("\nActive Directed Communication Edges:")
    for edge in matrix["edges"]:
        print(f"  * {edge['source']:<13}  -->  {edge['target']:<13} ({edge['count']} msgs) | Last: \"{edge['last_topic']}\"")

    print_banner("PHASE 4 AGENT-TO-AGENT COMMUNICATION DEMONSTRATION COMPLETE")


if __name__ == "__main__":
    run_demo()

