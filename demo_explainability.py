"""Interactive demonstration of Explainable Decisions & Logging (Phase 10)."""

import sys
from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import GlobalHomeState
from backend.agents.schemas import AgentType, AgentAlert
from backend.explainability import ExplanationEngine, AuditLogger, SafetyTier


def print_sep(char="=", length=78):
    print(char * length)


def run_demo():
    print_sep()
    print(" HomeMind - Multi-Agent AI Home Management System")
    print(" Phase 10: Explainable Decisions & Comprehensive Logging (Sections 13 & 16)")
    print_sep()

    logger = AuditLogger()
    sim = HomeSimulator()
    sim.set_global_home_state(GlobalHomeState.AWAY)
    for r in sim.rooms.values():
        r.occupied = False

    # 1. Section 13 Canonical Example: Water Leak Incident
    print("\n>>> EXPLAINABLE CARD 1: SECTION 13 CANONICAL WATER LEAK ALERT <<<")
    alert = AgentAlert(
        agent_type=AgentType.HOME_MANAGER,
        title="Possible water leakage detected.",
        severity="CRITICAL",
        description="Abnormal hydraulic outflow detected while residence is vacant."
    )
    exp1 = ExplanationEngine.explain_water_leak_alert(alert, sim.get_snapshot(), leak_rate_lpm=4.2)
    logger.log_decision(exp1)

    print(f"Title       : {exp1.title}")
    print(f"Type        : {exp1.decision_type} (Origin: {exp1.origin_agent.value})")
    print(f"Safety Tier : {exp1.safety_tier.value} (Section 16)")
    print(f"Summary     : {exp1.summary}")
    print("\nWhy?")
    for point in exp1.why_points:
        print(f"  - {point}")
    if exp1.recommended_action:
        print(f"\nRecommended Action: {exp1.recommended_action}")
    print_sep("-")

    # 2. Section 13 Example: Energy Load Shedding Decision
    print("\n>>> EXPLAINABLE CARD 2: DISCRETIONARY POWER SHEDDING <<<")
    exp2 = ExplanationEngine.explain_energy_shedding(
        device_name="Living Room Main Light",
        room_name="Living Room",
        watts_saved=20.0,
        reason="Vacant room policy",
        is_peak=True
    )
    logger.log_decision(exp2)

    print(f"Title       : {exp2.title}")
    print(f"Type        : {exp2.decision_type} (Origin: {exp2.origin_agent.value})")
    print(f"Safety Tier : {exp2.safety_tier.value}")
    print(f"Summary     : {exp2.summary}")
    print("\nWhy?")
    for point in exp2.why_points:
        print(f"  - {point}")
    print_sep("-")

    # 3. Section 13 Example: Conflict Resolution Arbitration
    print("\n>>> EXPLAINABLE CARD 3: MULTI-AGENT CONFLICT ARBITRATION <<<")
    exp3 = ExplanationEngine.explain_conflict_resolution(
        target_device="ac_living",
        chosen_agent=AgentType.COMFORT,
        chosen_action="SET_TEMP 24.0C",
        overruled_agent=AgentType.ENERGY,
        overruled_action="TURN_OFF",
        reason="Living room actively occupied by Alex Morgan in HOME mode."
    )
    logger.log_decision(exp3)

    print(f"Title       : {exp3.title}")
    print(f"Type        : {exp3.decision_type} (Origin: {exp3.origin_agent.value})")
    print(f"Safety Tier : {exp3.safety_tier.value}")
    print(f"Summary     : {exp3.summary}")
    print("\nWhy?")
    for point in exp3.why_points:
        print(f"  - {point}")
    print_sep("-")

    # 4. Audit Log Summary
    print("\nAudit Log Disk Locations:")
    print(f"  * JSONL Log : {logger.jsonl_path}")
    print(f"  * CSV Audit : {logger.csv_path}")
    print(f"  * Buffered  : {len(logger.memory_buffer)} explainable records active in memory")
    print_sep()

    print("\n[OK] Phase 10 Explainable Decisions & Logging verified successfully!")


if __name__ == "__main__":
    run_demo()

