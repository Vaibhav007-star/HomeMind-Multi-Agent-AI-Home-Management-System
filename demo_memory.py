"""Interactive demonstration of Shared Home State Machine & Contextual Memory (Phase 5 & 6)."""

from datetime import datetime
from backend.simulation import HomeSimulator, GlobalHomeState
from backend.agents import HomeManagerAgent


def print_banner(title: str):
    print("\n" + "=" * 72)
    print(f"   {title}")
    print("=" * 72)


def run_demo():
    print_banner("HomeMind — Phase 5 & 6: Shared Home State & Contextual Memory Demo")
    sim = HomeSimulator(start_hour=8, start_minute=30)
    manager = HomeManagerAgent()

    # 1. Section 4: Home State Machine & Operational Policy Profiles
    print_banner("PART 1: Section 4 — Global Home State Machine & Operational Policies")
    sm = manager.state_machine
    print(f"Current State: {sm.current_state.value}")
    policy = sm.get_active_policy()
    print(f"Active Operational Policy: {policy.description}")
    print(f"  * Security Armed: {policy.security_armed} | Max Discretionary Watts: {policy.max_discretionary_watts}W")

    # State transition HOME -> AWAY
    print("\n[Executing State Transition]: HOME -> AWAY")
    ok, tr = sm.transition_to(GlobalHomeState.AWAY, reason="Resident left for college", initiator="Resident")
    print(f"Transition Success: {ok} | Record ID: {tr.transition_id}")
    new_policy = sm.get_active_policy()
    print(f"New Operational Policy: {new_policy.description}")
    print(f"  * Security Armed: {new_policy.security_armed} | Strict Perimeter: {new_policy.strict_perimeter} | Max Discretionary Watts: {new_policy.max_discretionary_watts}W")

    # Transition integrity test
    print("\n[Testing Invalid Transition]: AWAY -> SLEEP (Direct Jump Disallowed)")
    can_jump = sm.can_transition(GlobalHomeState.SLEEP)
    print(f"Can transition directly from AWAY to SLEEP? {can_jump} (Rejected by State Machine)")

    # 2. Section 5: Structured Contextual Memory & Habit Recognition
    print_banner("PART 2: Section 5 — Contextual Habit Memory & Routine Correlation")
    memory = manager.memory

    # Morning departure habit (08:30 AM)
    sim_morning = datetime(2026, 9, 17, 8, 30, 0)
    is_habit, morning_expl = memory.get_departure_context(sim_morning)
    print(f"[Observation at {sim_morning.strftime('%I:%M %p')}]:")
    print(f"  * Matches Schedule Habit: {is_habit}")
    print(f"  * Contextual Reasoning: \"{morning_expl}\"")

    # Middle-of-the-night unscheduled event (02:15 AM)
    sim_night = datetime(2026, 9, 17, 2, 15, 0)
    is_habit_night, night_expl = memory.get_departure_context(sim_night)
    print(f"\n[Observation at {sim_night.strftime('%I:%M %p')}]:")
    print(f"  * Matches Schedule Habit: {is_habit_night}")
    print(f"  * Contextual Reasoning: \"{night_expl}\"")

    # 3. End-to-End Workflow with Contextual Memory
    print_banner("PART 3: End-to-End Workflow with Habit Memory Integration")
    workflow_result = manager.execute_workflow("I'm leaving for college.", sim)

    print("\nWorkflow Activity Timeline (Contextual Memory highlighted):")
    for item in workflow_result.timeline:
        print(f"  {item['time']} | {item['source']:<18} -> {item['event']}")

    # 4. Structured Memory Summary
    print_banner("PART 4: Structured Memory Snapshot & Decision History")
    mem_profile = manager.get_memory_summary()
    print(f"Resident Profile: {mem_profile['memory_summary']['resident_name']}")
    print(f"Thermal Comfort Preferences: {mem_profile['memory_summary']['preferences']['temp_min']}°C - {mem_profile['memory_summary']['preferences']['temp_max']}°C (Sleep: {mem_profile['memory_summary']['preferences']['sleep_temp']}°C)")
    print(f"Tracked Schedule Habits: {mem_profile['memory_summary']['tracked_habits_count']}")
    print(f"Archived Coordinator Decisions: {mem_profile['memory_summary']['decisions_archived_count']}")
    print(f"Operational Baselines: {mem_profile['memory_summary']['baselines']}")

    print_banner("PHASE 5 & 6 SHARED STATE & CONTEXTUAL MEMORY DEMO COMPLETE")


if __name__ == "__main__":
    run_demo()

