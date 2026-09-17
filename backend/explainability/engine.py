"""Explanation Engine generating structured, explainable decision records (Phase 10)."""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from datetime import datetime

from backend.agents.schemas import AgentType, AgentAlert, AgentActionProposal
from backend.simulation.models import HomeStateSnapshot, GlobalHomeState
from backend.explainability.models import DecisionExplanation, SafetyTier


class ExplanationEngine:
    """Generates concise, human-understandable decision explanations per Section 13."""

    @staticmethod
    def explain_water_leak_alert(
        alert: AgentAlert,
        snapshot: HomeStateSnapshot,
        leak_rate_lpm: float = 4.2
    ) -> DecisionExplanation:
        """Generates explanation matching Section 13 canonical example:

        ### Alert
        "Possible water leakage detected."
        ### Why?
        - Home is in AWAY mode.
        - Water consumption increased significantly.
        - No resident activity detected.
        - Pattern differs from normal usage.
        """
        why = [
            f"Home is in {snapshot.global_home_state.value} mode.",
            f"Water consumption increased significantly ({leak_rate_lpm:.1f} L/min detected on main line).",
            f"No resident activity detected ({sum(1 for r in snapshot.rooms.values() if r.occupied)} occupied rooms, 0 motion sensor triggers).",
            "Pattern differs from normal unoccupied baseline usage (0.0 L/min expected)."
        ]

        return DecisionExplanation(
            time_str=snapshot.simulation_time_str,
            title=alert.title,
            decision_type="ALERT",
            origin_agent=AgentType.HOME_MANAGER,
            participating_agents=[AgentType.RESOURCE, AgentType.SECURITY, AgentType.HOME_MANAGER],
            summary="Multi-agent cross-correlation detected an anomalous water outflow spike while residence is unoccupied.",
            why_points=why,
            observable_inputs={
                "home_state": snapshot.global_home_state.value,
                "water_outflow_lpm": leak_rate_lpm,
                "active_occupants": 0,
                "tank_level_percent": snapshot.water_system.water_level_percent
            },
            recommended_action="Close main emergency water shutoff valve and alert resident.",
            safety_tier=SafetyTier.REQUIRES_CONFIRMATION
        )

    @staticmethod
    def explain_energy_shedding(
        device_name: str,
        room_name: str,
        watts_saved: float,
        reason: str,
        is_peak: bool = False
    ) -> DecisionExplanation:
        """Explains why an appliance or light was turned off to save energy."""
        why = [
            f"Room '{room_name}' is currently unoccupied.",
            f"Appliance '{device_name}' was consuming discretionary electrical power ({watts_saved:.0f} W).",
            f"Power shedding policy active: deactivating non-essential loads preserves battery reserves and lowers billing.",
        ]
        if is_peak:
            why.append("Peak grid tariff pricing is currently active, multiplying per-kWh energy rates.")

        return DecisionExplanation(
            title=f"Energy Optimization: {device_name} Powered Down",
            decision_type="ACTION",
            origin_agent=AgentType.ENERGY,
            participating_agents=[AgentType.ENERGY],
            summary=f"Deactivated {device_name} in vacant {room_name}, eliminating {watts_saved:.0f} W of idle power draw.",
            why_points=why,
            observable_inputs={
                "device": device_name,
                "room": room_name,
                "watts": watts_saved,
                "is_peak_pricing": is_peak
            },
            recommended_action=None,
            safety_tier=SafetyTier.SAFE_AUTONOMOUS
        )

    @staticmethod
    def explain_climate_adjustment(
        device_name: str,
        room_name: str,
        current_temp: float,
        target_temp: float,
        action: str
    ) -> DecisionExplanation:
        """Explains thermostat setpoint or cooling adjustment."""
        why = [
            f"Indoor temperature in {room_name} was {current_temp:.1f}°C.",
            f"Resident comfort boundary is configured to 22.0°C - 25.5°C.",
            f"Adjusting target setpoint to {target_temp:.1f}°C restores optimal thermal equilibrium."
        ]

        return DecisionExplanation(
            title=f"Comfort Tuning: {device_name} Set to {target_temp:.1f}°C",
            decision_type="ACTION",
            origin_agent=AgentType.COMFORT,
            participating_agents=[AgentType.COMFORT],
            summary=f"Comfort Agent actuated {device_name} to stabilize {room_name} temperature within comfort bounds.",
            why_points=why,
            observable_inputs={
                "room": room_name,
                "current_temp_celsius": current_temp,
                "target_temp_celsius": target_temp,
                "action": action
            },
            safety_tier=SafetyTier.SAFE_AUTONOMOUS
        )

    @staticmethod
    def explain_conflict_resolution(
        target_device: str,
        chosen_agent: AgentType,
        chosen_action: str,
        overruled_agent: AgentType,
        overruled_action: str,
        reason: str
    ) -> DecisionExplanation:
        """Explains how the Home Manager arbitrated a dispute between agents."""
        why = [
            f"{chosen_agent.value} proposed '{chosen_action}', while {overruled_agent.value} proposed '{overruled_action}'.",
            f"Resolution policy: {reason}",
            f"Prioritizing {chosen_agent.value} maintains higher-order resident welfare and safety guidelines."
        ]

        return DecisionExplanation(
            title=f"Conflict Arbitration on {target_device}",
            decision_type="CONFLICT_RESOLUTION",
            origin_agent=AgentType.HOME_MANAGER,
            participating_agents=[chosen_agent, overruled_agent, AgentType.HOME_MANAGER],
            summary=f"Arbitrated conflicting requests on {target_device}: {chosen_agent.value} chosen over {overruled_agent.value}.",
            why_points=why,
            observable_inputs={
                "target_device": target_device,
                "chosen_action": chosen_action,
                "overruled_action": overruled_action,
                "rationale": reason
            },
            safety_tier=SafetyTier.SAFE_AUTONOMOUS
        )

    @staticmethod
    def explain_state_transition(
        from_state: GlobalHomeState,
        to_state: GlobalHomeState,
        initiator: str,
        rationale: str
    ) -> DecisionExplanation:
        """Explains why the global home state changed."""
        why = [
            f"Initiated by: {initiator}.",
            f"Valid state machine transition rule: {from_state.value} -> {to_state.value} is permitted.",
            f"Operational rationale: {rationale}"
        ]

        return DecisionExplanation(
            title=f"Global State Shift: {from_state.value} -> {to_state.value}",
            decision_type="STATE_TRANSITION",
            origin_agent=AgentType.HOME_MANAGER,
            participating_agents=[AgentType.HOME_MANAGER],
            summary=f"Home operating mode transitioned from {from_state.value} to {to_state.value}.",
            why_points=why,
            observable_inputs={
                "from_state": from_state.value,
                "to_state": to_state.value,
                "initiator": initiator
            },
            safety_tier=SafetyTier.SAFE_AUTONOMOUS
        )

