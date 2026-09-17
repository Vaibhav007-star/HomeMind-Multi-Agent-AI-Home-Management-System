"""Energy Management Agent implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from datetime import datetime

from backend.simulation.models import (
    HomeStateSnapshot,
    GlobalHomeState,
    DeviceType,
    DevicePowerState
)
from backend.agents.base import BaseAgent
from backend.agents.schemas import (
    AgentType,
    AgentStatusEnum,
    ActionPriority,
    AgentActionProposal,
    AgentAlert,
    AgentEvaluationResult
)
from backend.agents.orchestration import DelegationTask, AgentTaskResult
from backend.agents.communication import AgentMessage, MessageType


class EnergyAgent(BaseAgent):
    """Specialized Agent responsible for monitoring and optimizing home energy usage."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.ENERGY,
            name="Energy Agent",
            role="Power & Load Optimization",
            goal="Optimize electricity usage while maintaining acceptable home comfort"
        )
        self.peak_warning_threshold_watts = 3200.0  # Alert if load exceeds 3.2 kW

    def evaluate(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> AgentEvaluationResult:
        self.status = AgentStatusEnum.OPTIMIZING
        self.current_task = "Analyzing power telemetry & detecting energy waste"
        recommendations: List[AgentActionProposal] = []
        alerts: List[AgentAlert] = []

        instant_watts = snapshot.energy_system.instant_power_watts
        home_state = snapshot.global_home_state

        # 1. Peak power alert check
        if instant_watts >= self.peak_warning_threshold_watts:
            alert = AgentAlert(
                agent_type=self.agent_type,
                title="High Electrical Demand Alert",
                severity="WARNING",
                description=f"Instant power demand ({instant_watts:.0f} W) exceeds warning threshold ({self.peak_warning_threshold_watts:.0f} W).",
                evidence=[
                    f"Current power draw: {instant_watts:.1f} W",
                    f"Threshold: {self.peak_warning_threshold_watts} W",
                    f"Daily accumulated consumption: {snapshot.energy_system.daily_energy_kwh:.2f} kWh"
                ],
                recommended_action="Shed discretionary high-wattage loads."
            )
            alerts.append(alert)
            self.important_event = f"High power alert: {instant_watts:.0f}W"

        # 2. Check for wasted energy in vacant rooms
        for dev_id, dev in snapshot.devices.items():
            if dev.power_state != DevicePowerState.ON:
                continue

            room = snapshot.rooms.get(dev.room_id)
            is_vacant = (room is not None and not room.occupied) or (home_state == GlobalHomeState.AWAY)

            # AC running in a vacant room
            if dev.device_type == DeviceType.AC and is_vacant:
                rec = AgentActionProposal(
                    agent_type=self.agent_type,
                    target_type="device",
                    target_id=dev.id,
                    action="TURN_OFF",
                    priority=ActionPriority.HIGH if home_state == GlobalHomeState.AWAY else ActionPriority.MEDIUM,
                    reason=f"Air conditioner in {dev.room_id.replace('_', ' ').title()} is drawing {dev.power_draw_watts:.0f}W while room is unoccupied.",
                    explainable_evidence=[
                        f"Room '{dev.room_id}' occupancy is False",
                        f"AC '{dev.name}' is ON drawing {dev.power_draw_watts:.1f}W",
                        f"Home state: {home_state.value}"
                    ]
                )
                recommendations.append(rec)

            # TV left on in vacant room
            elif dev.device_type == DeviceType.TV and is_vacant:
                rec = AgentActionProposal(
                    agent_type=self.agent_type,
                    target_type="device",
                    target_id=dev.id,
                    action="TURN_OFF",
                    priority=ActionPriority.HIGH if home_state == GlobalHomeState.AWAY else ActionPriority.LOW,
                    reason=f"TV '{dev.name}' is ON in unoccupied room drawing {dev.power_draw_watts:.0f}W.",
                    explainable_evidence=[
                        f"Room '{dev.room_id}' is unoccupied",
                        f"TV is actively powered on"
                    ]
                )
                recommendations.append(rec)

            # Lights left on in vacant rooms
            elif dev.device_type == DeviceType.LIGHT and is_vacant and dev.room_id != "entrance":
                rec = AgentActionProposal(
                    agent_type=self.agent_type,
                    target_type="device",
                    target_id=dev.id,
                    action="TURN_OFF",
                    priority=ActionPriority.MEDIUM if home_state == GlobalHomeState.AWAY else ActionPriority.LOW,
                    reason=f"Lighting '{dev.name}' left ON in unoccupied {dev.room_id.replace('_', ' ').title()}.",
                    explainable_evidence=[
                        f"Room '{dev.room_id}' occupancy is False",
                        f"Light is ON drawing {dev.power_draw_watts:.1f}W"
                    ]
                )
                recommendations.append(rec)

        # 3. Overall Home state optimizations
        if home_state == GlobalHomeState.AWAY and instant_watts > 400.0:
            alerts.append(AgentAlert(
                agent_type=self.agent_type,
                title="Excessive Power Usage in AWAY Mode",
                severity="WARNING",
                description=f"Home is in AWAY state but consuming {instant_watts:.0f} W of electrical power.",
                evidence=[
                    "Home state is AWAY (residents absent)",
                    f"Power consumption is {instant_watts:.1f} W (expected < 250 W baseline for idle fridge/standby)"
                ],
                recommended_action="Power down non-essential active appliances."
            ))

        # Summarize decision
        if recommendations:
            self.latest_decision = f"Identified {len(recommendations)} potential energy-saving opportunities."
        else:
            self.latest_decision = f"Power consumption optimal ({instant_watts:.0f} W)."

        summary = (
            f"Power: {instant_watts:.0f}W ({snapshot.energy_system.instant_power_kw:.2f}kW). "
            f"Found {len(recommendations)} conservation actions, {len(alerts)} alerts."
        )

        return AgentEvaluationResult(
            agent_type=self.agent_type,
            agent_name=self.name,
            status=self.status,
            current_task=self.current_task,
            summary=summary,
            recommendations=recommendations,
            alerts=alerts,
            metrics={
                "instant_watts": instant_watts,
                "instant_kw": snapshot.energy_system.instant_power_kw,
                "daily_kwh": snapshot.energy_system.daily_energy_kwh,
                "peak_watts": snapshot.energy_system.peak_draw_watts,
                "wasted_loads_count": len(recommendations)
            }
        )

    def handle_task(self, task: DelegationTask, simulator: Any) -> AgentTaskResult:
        """Executes task delegated by Home Manager."""
        self.status = AgentStatusEnum.OPTIMIZING
        self.current_task = f"Executing delegated task: {task.command}"
        actions_executed: List[str] = []

        if task.command in ["DEACTIVATE_UNNECESSARY_LOADS", "OPTIMIZE_AWAY_ENERGY"]:
            initial_power = sum(d.get_current_power_draw() for d in simulator.devices.values())
            # Turn off TVs, Lights in living/kitchen/bedroom, ACs in vacant rooms
            for dev_id, dev in simulator.devices.items():
                if dev.power_state == DevicePowerState.ON:
                    if dev.device_type in [DeviceType.TV, DeviceType.LIGHT]:
                        if dev_id != "light_entrance":
                            dev.turn_off()
                            actions_executed.append(f"Turned OFF {dev.name} ({dev.room_id})")
                    elif dev.device_type == DeviceType.AC and task.parameters.get("all_vacant", False):
                        dev.turn_off()
                        actions_executed.append(f"Turned OFF {dev.name} ({dev.room_id})")

            saved_watts = initial_power - sum(d.get_current_power_draw() for d in simulator.devices.values())
            report = f"Deactivated {len(actions_executed)} discretionary loads, saving {saved_watts:.0f} W."
            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=actions_executed,
                report=report,
                data={"saved_watts": round(saved_watts, 1), "actions_count": len(actions_executed)}
            )

        elif task.command == "EXPLAIN_ENERGY_USAGE":
            # Rank active devices by wattage
            consumers = []
            for dev_id, dev in simulator.devices.items():
                draw = dev.get_current_power_draw()
                if draw > 0:
                    consumers.append({"name": dev.name, "room": dev.room_id, "watts": draw})

            consumers.sort(key=lambda x: x["watts"], reverse=True)
            total_draw = sum(c["watts"] for c in consumers)

            lines = [f"Total demand is {total_draw:.0f} W ({total_draw/1000:.2f} kW)."]
            for c in consumers[:4]:
                lines.append(f"- {c['name']} ({c['room']}): {c['watts']:.0f} W ({(c['watts']/total_draw)*100:.1f}%)")

            report = " ".join(lines)
            self.latest_decision = f"Analyzed energy consumption for {len(consumers)} active loads."

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=[],
                report=report,
                data={"total_watts": total_draw, "top_consumers": consumers[:5]}
            )

        return AgentTaskResult(
            task_id=task.task_id,
            agent_type=self.agent_type,
            success=False,
            report=f"Unrecognized energy command: {task.command}"
        )

    def propose_climate_tradeoff(
        self,
        target_ac_id: str,
        proposed_setpoint: float,
        current_temp: float,
        comfort_agent: BaseAgent,
        simulator: Any
    ) -> Optional[AgentMessage]:
        """Direct negotiation with Comfort Agent (Section 3 Example 1).

        Proposes adjusting AC setpoint to curb excessive energy usage while respecting comfort bounds.
        """
        ac = simulator.devices.get(target_ac_id)
        ac_name = ac.name if ac else target_ac_id
        draw = ac.get_current_power_draw() if ac else 1400.0

        content = (
            f"Energy consumption is unusually high because {ac_name} is consuming {draw:.0f}W. "
            f"Proposing raising thermostat to {proposed_setpoint:.1f}°C to save energy."
        )

        proposal = self.send_message(
            receiver=AgentType.COMFORT,
            msg_type=MessageType.NEGOTIATION_PROPOSAL,
            topic="CLIMATE_ENERGY_TRADEOFF",
            content=content,
            payload={
                "device_id": target_ac_id,
                "current_draw_watts": draw,
                "proposed_setpoint": proposed_setpoint,
                "current_temp": current_temp
            }
        )

        if proposal:
            self.important_event = f"Negotiating {ac_name} setpoint with Comfort Agent"
            # Route directly to Comfort Agent to process negotiation
            response = comfort_agent.handle_incoming_message(proposal, simulator)
            if response and response.msg_type == MessageType.NEGOTIATION_COUNTER:
                agreed = response.payload.get("agreed_setpoint", proposed_setpoint)
                self.send_message(
                    receiver=AgentType.COMFORT,
                    msg_type=MessageType.NEGOTIATION_ACCEPT,
                    topic="CLIMATE_ENERGY_TRADEOFF",
                    content=f"Energy Agent accepts counter-proposal setpoint of {agreed:.1f}°C as an acceptable compromise.",
                    payload={"agreed_setpoint": agreed, "device_id": target_ac_id}
                )
            return response
        return None



