"""Interactive demonstration of Home Manager Delegation & Workflow Orchestration (Phase 3)."""

from backend.simulation import HomeSimulator, DevicePowerState
from backend.agents import HomeManagerAgent


def print_banner(title: str):
    print("\n" + "=" * 70)
    print(f"   {title}")
    print("=" * 70)


def print_workflow_result(result):
    print(f"\n[USER PROMPT]: \"{result.user_prompt}\"")
    print(f"[PARSED INTENT]: {result.intent}")
    print(f"[DELEGATION RATIONALE]: {result.delegation_plan.rationale}")
    
    print("\n--- AGENT DELEGATION EXECUTION ---")
    for agent_name, res in result.agent_results.items():
        status_sym = "[OK]" if res.success else "[FAIL]"
        print(f"{status_sym} {agent_name.replace('_', ' ').title()} Agent:")
        print(f"    Report: {res.report}")
        if res.actions_executed:
            print(f"    Actions Actuated: {', '.join(res.actions_executed)}")

    print("\n--- SECTION 10: AGENT ACTIVITY TIMELINE ---")
    for item in result.timeline:
        print(f"  {item['time']} | {item['source']:<16} -> {item['event']}")

    print("\n" + "-" * 70)
    print(result.final_response)
    print("-" * 70)


def run_demo():
    print_banner("HomeMind — Phase 3: Home Manager Delegation & Orchestration Demo")
    sim = HomeSimulator(start_hour=8, start_minute=30)
    manager = HomeManagerAgent()

    # Pre-condition: Some appliances running
    sim.set_device_power("tv_living", DevicePowerState.ON)
    sim.set_device_power("ac_living", DevicePowerState.ON)
    sim.set_device_power("light_kitchen", DevicePowerState.ON)
    sim.set_lock_state(False)

    # 1. User Leaving Home
    print_banner("DEMO 1: Section 3 Example 3 — 'I am leaving for college'")
    res1 = manager.execute_workflow("I'm leaving for college.", sim)
    print_workflow_result(res1)

    # 2. Querying Energy Usage
    print_banner("DEMO 2: Section 12 — 'Why is the energy consumption high?'")
    sim.set_device_power("ac_bedroom", DevicePowerState.ON)
    sim.devices["ac_bedroom"].attributes["compressor_active"] = True
    res2 = manager.execute_workflow("Why is the energy consumption high?", sim)
    print_workflow_result(res2)

    # 3. Sleep Mode Request
    print_banner("DEMO 3: Section 12 — 'Turn the house into sleep mode'")
    res3 = manager.execute_workflow("Turn the house into sleep mode.", sim)
    print_workflow_result(res3)

    # 4. Security & Safety Query
    print_banner("DEMO 4: Section 12 — 'Is everything okay at home?'")
    res4 = manager.execute_workflow("Is everything okay at home?", sim)
    print_workflow_result(res4)

    # 5. Grocery & Supplies Query
    print_banner("DEMO 5: Section 12 — 'Do we need to buy anything?'")
    res5 = manager.execute_workflow("Do we need to buy anything?", sim)
    print_workflow_result(res5)

    print_banner("PHASE 3 HOME MANAGER DELEGATION DEMONSTRATION COMPLETE")


if __name__ == "__main__":
    run_demo()
