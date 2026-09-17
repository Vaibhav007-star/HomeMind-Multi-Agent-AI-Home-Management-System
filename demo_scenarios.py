"""Interactive CLI demonstration for HomeMind Phase 7 Scenarios."""

import sys
from backend.scenarios.runner import ScenarioRunner


def print_separator(char="=", length=78):
    print(char * length)


def run_demo():
    print_separator()
    print(" HomeMind - Multi-Agent AI Home Management System")
    print(" Phase 7: Three Major Demonstration Scenarios (Section 8)")
    print_separator()

    runner = ScenarioRunner()
    results = runner.run_all()

    for key, report in results.items():
        clean_title = report.title.replace("—", "--").upper()
        print(f"\n>>> {clean_title} <<<")
        print(f"Description : {report.description}")
        print(f"Time Range  : {report.sim_time_start} -> {report.sim_time_end}")
        print(f"State Cycle : {report.initial_state} -> {report.final_state}")
        print_separator("-")

        print("Timeline & Execution Steps:")
        for step in report.steps:
            badge = f"[{step.action_type}]"
            print(f"  [{step.step_index:02d}] {step.time_str} {badge:<14} {step.actor}")
            print(f"       -> {step.description}")
            if step.evidence:
                print(f"       [Evidence]: {'; '.join(step.evidence)}")

        if report.alerts:
            print("\nGenerated Cross-Agent Alerts:")
            for alert in report.alerts:
                agent_lbl = alert.agent_type.value if hasattr(alert.agent_type, 'value') else str(alert.agent_type)
                print(f"  * [{alert.severity}] {alert.title} (Source: {agent_lbl})")
                print(f"    Description: {alert.description}")
                for ev in alert.evidence:
                    print(f"    - Evidence: {ev}")

        print("\nAgent Domain Summaries:")
        for agent, summary in report.agent_summaries.items():
            print(f"  * {agent:<15}: {summary}")

        print("\nExplainability & Synthesis:")
        print(f"  {report.explainability_summary}")
        print_separator()

    print("\n[OK] Phase 7 Demonstration successfully completed for all 3 scenarios!")


if __name__ == "__main__":
    run_demo()
