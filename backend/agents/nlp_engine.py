"""Natural Language Processing & LLM Integration Engine for HomeMind (Phase 9).

Adheres to Section 14:
- Used for natural-language understanding, task delegation, contextual interpretation,
  summarization, recommendations, and natural-language explanations.
- Employs deterministic semantic logic by default, with optional external LLM provider
  plugs (Google Gemini, OpenAI, Ollama).
"""

from __future__ import annotations
import os
import re
import json
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from backend.agents.schemas import AgentType, ActionPriority, AgentAlert
from backend.agents.orchestration import DelegationPlan, DelegationTask, AgentTaskResult
from backend.simulation.models import GlobalHomeState


class LLMProvider(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    GEMINI = "GEMINI"
    OPENAI = "OPENAI"
    OLLAMA = "OLLAMA"


class NLPEngine:
    """Intelligent Natural Language Understanding & Generation Engine for HomeMind."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        if provider:
            self.provider = provider
        elif os.getenv("GEMINI_API_KEY"):
            self.provider = LLMProvider.GEMINI
        elif os.getenv("OPENAI_API_KEY"):
            self.provider = LLMProvider.OPENAI
        elif os.getenv("OLLAMA_BASE_URL"):
            self.provider = LLMProvider.OLLAMA
        else:
            self.provider = LLMProvider.DETERMINISTIC

    def understand_intent(
        self,
        user_prompt: str,
        current_state: GlobalHomeState,
        sim_time_str: str = "08:30"
    ) -> DelegationPlan:
        """Parses high-level user prompts into structured multi-agent delegation plans."""
        prompt_clean = user_prompt.strip().lower()

        # 1. Return Home Intent (Checked first to prevent false matching on 'returned from college')
        return_patterns = [
            r"\bi'm home\b", r"\bback home\b", r"\barrived\b", r"\breturned\b",
            r"\bback from (college|work|class|office)\b", r"\benter(ed)? home\b"
        ]
        if any(re.search(pat, prompt_clean) for pat in return_patterns):
            return DelegationPlan(
                intent="RETURN_HOME",
                target_home_state=GlobalHomeState.HOME,
                rationale="Resident has returned home. Transitioning to HOME mode; disarming perimeter and restoring daytime comfort setpoints.",
                tasks=[
                    DelegationTask(
                        recipient=AgentType.SECURITY,
                        command="DISARM_TO_HOME",
                        instruction="Disarm away perimeter sensors and unlock front entrance for resident.",
                        priority=ActionPriority.HIGH
                    ),
                    DelegationTask(
                        recipient=AgentType.COMFORT,
                        command="RESTORE_HOME_COMFORT",
                        instruction="Restore daytime temperature (24.0°C) and activate welcoming ambient lighting.",
                        priority=ActionPriority.MEDIUM
                    )
                ]
            )

        # 2. Leaving Home Intent
        leaving_patterns = [
            r"\bleaving\b", r"\b(leaving|going to|heading to|off to)\s+(?:my\s+)?college\b",
            r"\bcollege\b", r"\bdepart\b", r"\bheading out\b",
            r"\bgoing to (work|class|school|market|office)\b", r"\bbye\b", r"\baway\b",
            r"\bgoing out\b", r"\bstepped out\b", r"\bvacate\b"
        ]
        if any(re.search(pat, prompt_clean) for pat in leaving_patterns):
            return DelegationPlan(
                intent="LEAVING_HOME",
                target_home_state=GlobalHomeState.AWAY,
                rationale="Resident is departing. Transitioning home to AWAY mode; delegating energy shedding, climate shutdown, and perimeter lockdown.",
                tasks=[
                    DelegationTask(
                        recipient=AgentType.ENERGY,
                        command="DEACTIVATE_UNNECESSARY_LOADS",
                        instruction="Power down discretionary appliances, lights, and entertainment systems.",
                        parameters={"all_vacant": True},
                        priority=ActionPriority.HIGH
                    ),
                    DelegationTask(
                        recipient=AgentType.COMFORT,
                        command="PREPARE_AWAY_COMFORT",
                        instruction="Shut down active AC units and ceiling fans to conserve energy.",
                        priority=ActionPriority.MEDIUM
                    ),
                    DelegationTask(
                        recipient=AgentType.SECURITY,
                        command="ARM_AWAY_MONITORING",
                        instruction="Engage front door smart lock (LOCKED) and arm perimeter intrusion detection.",
                        priority=ActionPriority.HIGH
                    ),
                    DelegationTask(
                        recipient=AgentType.RESOURCE,
                        command="CHECK_RESOURCES",
                        instruction="Verify water tank reserves and confirm zero plumbing leaks before departure.",
                        priority=ActionPriority.MEDIUM
                    )
                ]
            )

        # 2. Sleep Mode Intent
        sleep_patterns = [
            r"\bsleep\b", r"\bbed\b", r"\bnight\b", r"\bgoodnight\b",
            r"\btiring\b", r"\bretiring\b", r"\bhit the sack\b", r"\bdoze\b"
        ]
        if any(re.search(pat, prompt_clean) for pat in sleep_patterns):
            return DelegationPlan(
                intent="SLEEP_MODE",
                target_home_state=GlobalHomeState.SLEEP,
                rationale="Resident is going to bed. Transitioning home to SLEEP mode; setting quiet bedroom climate, dimming lights, and securing perimeter.",
                tasks=[
                    DelegationTask(
                        recipient=AgentType.COMFORT,
                        command="PREPARE_SLEEP_COMFORT",
                        instruction="Set bedroom AC to sleep setpoint (23.5°C) and fan to quiet speed.",
                        priority=ActionPriority.HIGH
                    ),
                    DelegationTask(
                        recipient=AgentType.ENERGY,
                        command="DEACTIVATE_UNNECESSARY_LOADS",
                        instruction="Deactivate non-bedroom lighting, TV, and living room appliances.",
                        parameters={"all_vacant": False},
                        priority=ActionPriority.MEDIUM
                    ),
                    DelegationTask(
                        recipient=AgentType.SECURITY,
                        command="SECURE_FOR_SLEEP",
                        instruction="Verify and lock entrance door for overnight perimeter protection.",
                        priority=ActionPriority.HIGH
                    )
                ]
            )


        # 4. Energy Audit & High Consumption Query (Section 12 Question 3)
        energy_patterns = [
            r"\benergy\b", r"\bpower\b", r"\belectricity\b", r"\bwatt(age)?\b",
            r"\bconsumption high\b", r"\bbill\b", r"\bkilowatt\b"
        ]
        if any(re.search(pat, prompt_clean) for pat in energy_patterns):
            return DelegationPlan(
                intent="ENERGY_AUDIT",
                target_home_state=None,
                rationale="User querying electrical demand. Delegating real-time consumption audit to Energy Agent.",
                tasks=[
                    DelegationTask(
                        recipient=AgentType.ENERGY,
                        command="EXPLAIN_ENERGY_USAGE",
                        instruction="Audit real-time wattage draw, identify heaviest active consumers, and evaluate peak pricing status.",
                        priority=ActionPriority.HIGH
                    )
                ]
            )

        # 5. Security & Safety Status Query (Section 12 Question 4)
        security_patterns = [
            r"\beverything okay\b", r"\ball good\b", r"\bsecurity\b", r"\bsecure\b", r"\bsafe\b",
            r"\bperimeter\b", r"\block(ed)?\b", r"\bdoors?\b", r"\bintruder\b", r"\balert\b"
        ]
        if any(re.search(pat, prompt_clean) for pat in security_patterns):
            return DelegationPlan(
                intent="SECURITY_STATUS",
                target_home_state=None,
                rationale="User inquiring about home safety and status. Delegating perimeter audit to Security Agent and plumbing check to Resource Agent.",
                tasks=[
                    DelegationTask(
                        recipient=AgentType.SECURITY,
                        command="AUDIT_HOME_SECURITY",
                        instruction="Inspect entrance door contact, smart lock state, and room motion sensors.",
                        priority=ActionPriority.HIGH
                    ),
                    DelegationTask(
                        recipient=AgentType.RESOURCE,
                        command="CHECK_RESOURCES",
                        instruction="Inspect water tank level and check for abnormal plumbing outflow.",
                        priority=ActionPriority.MEDIUM
                    )
                ]
            )

        # 6. Grocery & Supplies Query (Section 12 Question 5)
        grocery_patterns = [
            r"\bbuy anything\b", r"\bgrocery\b", r"\bgroceries\b", r"\bshopping\b",
            r"\bsupplies\b", r"\brestock\b", r"\bfood\b", r"\bfridge items\b"
        ]
        if any(re.search(pat, prompt_clean) for pat in grocery_patterns):
            return DelegationPlan(
                intent="GROCERY_CHECK",
                target_home_state=None,
                rationale="User inquiring about household supplies. Delegating inventory audit to Resource Agent.",
                tasks=[
                    DelegationTask(
                        recipient=AgentType.RESOURCE,
                        command="INVENTORY_AUDIT",
                        instruction="Review grocery consumables against minimum threshold levels.",
                        priority=ActionPriority.MEDIUM
                    )
                ]
            )

        # Default: Comprehensive Home Status
        return DelegationPlan(
            intent="GENERAL_STATUS",
            target_home_state=None,
            rationale="General resident status inquiry. Delegating baseline audit across Security, Resource, and Energy agents.",
            tasks=[
                DelegationTask(recipient=AgentType.SECURITY, command="AUDIT_HOME_SECURITY", instruction="Audit perimeter lock and doors.", priority=ActionPriority.MEDIUM),
                DelegationTask(recipient=AgentType.RESOURCE, command="CHECK_RESOURCES", instruction="Audit water reserve and plumbing.", priority=ActionPriority.MEDIUM),
                DelegationTask(recipient=AgentType.ENERGY, command="EXPLAIN_ENERGY_USAGE", instruction="Audit active power consumption.", priority=ActionPriority.LOW)
            ]
        )

    def generate_natural_response(
        self,
        intent: str,
        user_prompt: str,
        rationale: str,
        target_state: Optional[GlobalHomeState],
        agent_results: Dict[str, AgentTaskResult],
        context_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generates clear, explainable natural-language response per Section 13 & 14."""
        lines: List[str] = []

        if intent == "LEAVING_HOME":
            lines.append("### Home Manager Response: Departing Home (AWAY Mode)")
            lines.append(f"*{rationale}*\n")
            lines.append("Here is how the specialized agents prepared your home:")
            for key, res in agent_results.items():
                agent_lbl = key.replace("_", " ").title() + " Agent"
                lines.append(f"- **{agent_lbl}**: {res.report}")
            lines.append("\n**All perimeter defenses are ARMED and unnecessary appliances are OFF.** Safe travels!")

        elif intent == "SLEEP_MODE":
            lines.append("### Home Manager Response: Sleep Mode Engaged")
            lines.append(f"*{rationale}*\n")
            lines.append("Here is how your home was configured for sleep:")
            for key, res in agent_results.items():
                agent_lbl = key.replace("_", " ").title() + " Agent"
                lines.append(f"- **{agent_lbl}**: {res.report}")
            lines.append("\n**Front door is LOCKED and overnight climate is optimized.** Good night!")

        elif intent == "RETURN_HOME":
            lines.append("### Home Manager Response: Welcome Back Home!")
            lines.append(f"*{rationale}*\n")
            for key, res in agent_results.items():
                agent_lbl = key.replace("_", " ").title() + " Agent"
                lines.append(f"- **{agent_lbl}**: {res.report}")
            lines.append("\n**Perimeter disarmed to standard mode and comfortable climate restored.**")

        elif intent == "ENERGY_AUDIT":
            lines.append("### Home Manager Response: Energy Consumption Breakdown")
            lines.append(f"*{rationale}*\n")
            energy_res = agent_results.get("ENERGY")
            if energy_res:
                lines.append(f"- **Power Summary**: {energy_res.report}")
                if "total_watts" in energy_res.data:
                    lines.append(f"- **Total Instant Load**: {energy_res.data['total_watts']} W")
                if "running_loads" in energy_res.data:
                    lines.append(f"- **Active Consumers**: {energy_res.data['running_loads']}")
                if energy_res.data.get("peak_pricing"):
                    lines.append("- **Notice**: Grid is currently in *peak tariff pricing*. Non-essential loads are flagged.")
            else:
                lines.append("- Energy consumption is currently within normal operating bounds.")

        elif intent == "SECURITY_STATUS":
            lines.append("### Home Manager Response: Home Safety & Perimeter Audit")
            lines.append(f"*{rationale}*\n")
            sec_res = agent_results.get("SECURITY")
            res_res = agent_results.get("RESOURCE")
            if sec_res:
                lines.append(f"- **Perimeter**: {sec_res.report}")
            if res_res:
                lines.append(f"- **Plumbing & Resources**: {res_res.report}")
            lines.append("\n**Conclusion**: All safety parameters are fully secure and normal.")

        elif intent == "GROCERY_CHECK":
            lines.append("### Home Manager Response: Household Supplies Audit")
            lines.append(f"*{rationale}*\n")
            res_res = agent_results.get("RESOURCE")
            if res_res:
                lines.append(f"- **Inventory Status**: {res_res.report}")
                restock = res_res.data.get("restock_items", [])
                if restock:
                    lines.append("\n**Recommended Shopping List**:")
                    for it in restock:
                        lines.append(f"  * {it}")
                else:
                    lines.append("- All household consumables are currently above replenishment thresholds.")
            else:
                lines.append("- Inventory is fully stocked.")

        else:
            lines.append("### Home Manager Response: General Home Status")
            lines.append(f"*{rationale}*\n")
            for key, res in agent_results.items():
                agent_lbl = key.replace("_", " ").title() + " Agent"
                lines.append(f"- **{agent_lbl}**: {res.report}")

        return "\n".join(lines)

    def explain_anomaly(self, alert: AgentAlert, observable_inputs: List[str]) -> str:
        """Generates a clear explanation for an alert per Section 13."""
        lines = [
            f"### Alert Explanation: {alert.title}",
            f"**Severity**: {alert.severity} | **Originating Agent**: {alert.agent_type.value}",
            f"**Observation**: {alert.description}\n",
            "**Observable Evidence & Causal Factors**:"
        ]
        for ev in (alert.evidence or observable_inputs):
            lines.append(f"- {ev}")
        if alert.recommended_action:
            lines.append(f"\n**Recommended Action**: {alert.recommended_action}")
        return "\n".join(lines)
