"""Interactive demonstration of the HomeMind Five Agent Architecture (Phase 2)."""

from backend.simulation import HomeSimulator, DevicePowerState, GlobalHomeState
from backend.agents import HomeManagerAgent, AgentType


def print_banner(title: str):
    print("\n" + "=" * 70)
    print(f"   {title}")
    print("=" * 70)


def print_agent_statuses(manager: HomeManagerAgent):
    print("\n--- 5-AGENT ARCHITECTURE STATUS MONITOR (Section 9) ---")
    all_agents = [manager] + list(manager.sub_agents.values())
    for ag in all_agents:
        info = ag.get_display_status()
        print(f"[{info['agent_type']:<13}] Status: {info['status']:<12} | Task: {info['current_task']}")
        print(f"                 Latest Decision: {info['latest_decision']}")


def run_demo():
    print_banner("HomeMind — Phase 2: Five Agent Architecture Demonstration")
    sim = HomeSimulator(start_hour=7, start_minute=30)
    manager = HomeManagerAgent()

    # 1. Baseline Agent Status
    print_agent_statuses(manager)

    # 2. Cycle 1: Typical Home Morning State
    print_banner("CYCLE 1: Multi-Agent Evaluation in Normal HOME State")
    # Simulate vacant kitchen with light left ON, warm occupied bedroom
    sim.set_occupancy("bedroom", True)
    sim.rooms["bedroom"].temperature_celsius = 27.2
    sim.set_device_power("ac_bedroom", DevicePowerState.OFF)

    sim.set_occupancy("kitchen", False)
    sim.set_device_power("light_kitchen", DevicePowerState.ON)

    sim.set_occupancy("living_room", False)
    sim.set_device_power("tv_living", DevicePowerState.ON)

    snapshot = sim.get_snapshot()
    decision = manager.coordinate_cycle(snapshot)

    print(f"\n[Home Manager Coordination Summary]:\n{decision.summary}")
    print("\nApproved Agent Action Proposals:")
    for act in decision.approved_actions:
        print(f"  * [{act.agent_type.value}] -> {act.action} on {act.target_id} ({act.priority.value} priority)")
        print(f"    Reason: {act.reason}")

    # 3. Cycle 2: Security Agent in Action (Intrusion in AWAY Mode)
    print_banner("CYCLE 2: Security Agent Perimeter Defense in AWAY Mode")
    sim.set_global_home_state(GlobalHomeState.AWAY)
    for r in sim.rooms:
        sim.set_occupancy(r, False)
    # Simulate front door opening while home is in AWAY state
    sim.set_door_state(True)

    snapshot = sim.get_snapshot()
    decision = manager.coordinate_cycle(snapshot)

    print(f"\n[Home Manager Response]: {decision.summary}")
    print("\nActive Security Alerts:")
    for alert in decision.active_alerts:
        print(f"  ! [{alert.severity}] {alert.title}")
        print(f"    Description: {alert.description}")
        print(f"    Explainable Evidence: {alert.evidence}")
        print(f"    Recommended Action: {alert.recommended_action}")

    # 4. Cycle 3: Cross-Agent Multi-Domain Synthesis (Water Leak while Away)
    print_banner("CYCLE 3: Cross-Agent Collaboration (Water Anomaly + Security State)")
    sim.set_door_state(False)  # Close door
    sim.trigger_scenario_water_leak()  # Injects 4.2 L/min leak while unoccupied

    snapshot = sim.get_snapshot()
    decision = manager.coordinate_cycle(snapshot)

    print(f"\n[Home Manager Decision Summary]:\n{decision.summary}")
    print("\nMulti-Agent Correlated Incident Analysis:")
    for alert in decision.active_alerts:
        print(f"  * [{alert.severity}] {alert.title}")
        print(f"    Explanation / Observable Evidence:")
        for ev in alert.evidence:
            print(f"      - {ev}")

    print_agent_statuses(manager)
    print_banner("PHASE 2 FIVE-AGENT ARCHITECTURE DEMONSTRATION COMPLETE")


if __name__ == "__main__":
    run_demo()

