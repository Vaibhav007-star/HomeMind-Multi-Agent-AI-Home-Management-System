"""Interactive demonstration of Natural-Language Interaction & NLP Engine (Phase 9)."""

import sys
from backend.simulation.simulator import HomeSimulator
from backend.agents.home_manager import HomeManagerAgent


def print_sep(char="=", length=78):
    print(char * length)


def run_demo():
    print_sep()
    print(" HomeMind - Multi-Agent AI Home Management System")
    print(" Phase 9: Natural-Language Interaction & LLM Integration (Sections 12 & 14)")
    print_sep()

    sim = HomeSimulator()
    manager = HomeManagerAgent()

    test_queries = [
        ("I'm leaving for college.", "Resident Departure (AWAY transition + habit correlation)"),
        ("Why is the energy consumption high?", "Energy Audit Query (Wattage analysis + active consumers)"),
        ("Turn the house into sleep mode.", "Sleep Mode Delegation (Overnight climate + perimeter lock)"),
        ("Is everything okay at home?", "Safety & Security Audit (Perimeter + plumbing check)"),
        ("Do we need to buy anything?", "Household Supplies Check (Resource inventory audit)"),
        ("I'm back home.", "Resident Return (Disarm perimeter + restore comfort)")
    ]

    for idx, (prompt, explanation) in enumerate(test_queries, 1):
        print(f"\n[{idx}/6] QUERY: \"{prompt}\"")
        print(f"Context Goal: {explanation}")
        print_sep("-")

        wf = manager.execute_workflow(prompt, sim)

        print(f"Intent Parsed : [{wf.intent}]")
        print(f"Target State  : {wf.target_home_state or 'None (Informational)'}")
        print(f"Actions Done  : {len(wf.actions_applied)} actions applied")
        print(f"Domain Tasks  : {len(wf.agent_results)} specialized agents engaged")
        print("\nManager Response:")
        print(wf.final_response)
        print_sep()

    print("\n[OK] Phase 9 Natural-Language Interaction verified successfully!")


if __name__ == "__main__":
    run_demo()

