"""Comfort Agent implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional, Any

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
from backend.simulation.devices import AirConditioner, SmartFan


class ComfortAgent(BaseAgent):
    """Specialized Agent responsible for environmental comfort, climate, and lighting."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.COMFORT,
            name="Comfort Agent",
            role="Environmental Comfort & Climate",
            goal="Maintain a comfortable living environment for residents"
        )
        # Standard comfort preferences (Alex Morgan preferred range 22.0°C - 25.5°C)
        self.preferred_temp_min = 22.0
        self.preferred_temp_max = 25.5
        self.target_climate_setpoint = 24.0

    def evaluate(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> AgentEvaluationResult:
        self.status = AgentStatusEnum.OPTIMIZING
        self.current_task = "Evaluating indoor thermal and lighting comfort"
        recommendations: List[AgentActionProposal] = []
        alerts: List[AgentAlert] = []

        home_state = snapshot.global_home_state

        for room_id, room in snapshot.rooms.items():
            # If room is occupied, comfort is top priority
            if room.occupied and home_state != GlobalHomeState.AWAY:
                # 1. Thermal Comfort Check
                if room.temperature_celsius > self.preferred_temp_max:
                    # Look for an AC in this room
                    ac_dev = next((d for d in snapshot.devices.values() if d.room_id == room_id and d.device_type == DeviceType.AC), None)
                    if ac_dev:
                        if ac_dev.power_state != DevicePowerState.ON:
                            recommendations.append(AgentActionProposal(
                                agent_type=self.agent_type,
                                target_type="device",
                                target_id=ac_dev.id,
                                action="TURN_ON",
                                parameters={"target_temp_celsius": self.target_climate_setpoint},
                                priority=ActionPriority.HIGH,
                                reason=f"{room.room_name} temperature ({room.temperature_celsius}°C) exceeds comfort ceiling ({self.preferred_temp_max}°C).",
                                explainable_evidence=[
                                    f"Room '{room.room_name}' is occupied",
                                    f"Current temp {room.temperature_celsius}°C > preferred max {self.preferred_temp_max}°C",
                                    f"AC '{ac_dev.name}' is currently OFF"
                                ]
                            ))
                        else:
                            # AC is on, check if target is appropriate
                            curr_target = float(ac_dev.attributes.get("target_temp_celsius", 24.0))
                            if curr_target > self.target_climate_setpoint:
                                recommendations.append(AgentActionProposal(
                                    agent_type=self.agent_type,
                                    target_type="device",
                                    target_id=ac_dev.id,
                                    action="SET_TEMP",
                                    parameters={"target_temp_celsius": self.target_climate_setpoint},
                                    priority=ActionPriority.MEDIUM,
                                    reason=f"Lower AC thermostat in {room.room_name} to {self.target_climate_setpoint}°C for optimal comfort.",
                                    explainable_evidence=[
                                        f"Current target {curr_target}°C is above recommended comfort target {self.target_climate_setpoint}°C"
                                    ]
                                ))

                # 2. Lighting Comfort Check in occupied room
                light_dev = next((d for d in snapshot.devices.values() if d.room_id == room_id and d.device_type == DeviceType.LIGHT), None)
                if light_dev and light_dev.power_state == DevicePowerState.OFF and home_state != GlobalHomeState.SLEEP:
                    # In evening or morning if room is occupied, turn on light
                    if snapshot.outdoor_temperature_celsius > 20.0 and room_id in ["living_room", "kitchen"]:
                        recommendations.append(AgentActionProposal(
                            agent_type=self.agent_type,
                            target_type="device",
                            target_id=light_dev.id,
                            action="TURN_ON",
                            priority=ActionPriority.MEDIUM,
                            reason=f"Activate lighting in occupied {room.room_name}.",
                            explainable_evidence=[
                                f"Room '{room.room_name}' is occupied",
                                f"Light '{light_dev.name}' is OFF"
                            ]
                        ))

            # If SLEEP mode is active
            if home_state == GlobalHomeState.SLEEP:
                # Dim or turn off living room/kitchen lights
                for dev in snapshot.devices.values():
                    if dev.device_type == DeviceType.LIGHT and dev.power_state == DevicePowerState.ON and dev.room_id != "entrance":
                        recommendations.append(AgentActionProposal(
                            agent_type=self.agent_type,
                            target_type="device",
                            target_id=dev.id,
                            action="TURN_OFF",
                            priority=ActionPriority.HIGH,
                            reason="Turn off non-essential lights for Sleep mode.",
                            explainable_evidence=["Global home state is SLEEP"]
                        ))

        # Check for abnormal thermal alert
        hottest_room = max(snapshot.rooms.values(), key=lambda r: r.temperature_celsius)
        if hottest_room.temperature_celsius >= 33.0 and hottest_room.occupied:
            alerts.append(AgentAlert(
                agent_type=self.agent_type,
                title="Heat Discomfort Alert",
                severity="WARNING",
                description=f"Severe heat in {hottest_room.room_name} ({hottest_room.temperature_celsius}°C).",
                evidence=[
                    f"{hottest_room.room_name} is occupied",
                    f"Room temperature: {hottest_room.temperature_celsius}°C (Comfort max: {self.preferred_temp_max}°C)"
                ],
                recommended_action="Activate cooling immediately."
            ))

        if recommendations:
            self.latest_decision = f"Proposed {len(recommendations)} comfort adjustments."
        else:
            self.latest_decision = "Indoor comfort levels are satisfactory."

        summary = f"Evaluated 5 rooms. Comfort state: {self.latest_decision} ({len(alerts)} alerts)."

        return AgentEvaluationResult(
            agent_type=self.agent_type,
            agent_name=self.name,
            status=self.status,
            current_task=self.current_task,
            summary=summary,
            recommendations=recommendations,
            alerts=alerts,
            metrics={
                "preferred_temp_target": self.target_climate_setpoint,
                "hottest_room": hottest_room.room_name,
                "hottest_room_temp": hottest_room.temperature_celsius,
                "active_comfort_actions": len(recommendations)
            }
        )

    def handle_task(self, task: DelegationTask, simulator: Any) -> AgentTaskResult:
        """Executes task delegated by Home Manager."""
        self.status = AgentStatusEnum.OPTIMIZING
        self.current_task = f"Executing delegated task: {task.command}"
        actions_executed: List[str] = []

        if task.command == "PREPARE_SLEEP_COMFORT":
            # Turn on bedroom AC at 23.5°C
            ac_bed = simulator.devices.get("ac_bedroom")
            if ac_bed and isinstance(ac_bed, AirConditioner):
                ac_bed.turn_on()
                ac_bed.set_target_temperature(23.5)
                actions_executed.append("Configured Bedroom AC to night comfort target (23.5°C)")

            # Set bedroom fan to quiet gentle speed (speed 1)
            fan_bed = simulator.devices.get("fan_bedroom")
            if fan_bed and isinstance(fan_bed, SmartFan):
                fan_bed.set_speed(1)
                actions_executed.append("Adjusted Bedroom fan to gentle night speed (1)")

            # Turn off living room comfort devices
            if "ac_living" in simulator.devices:
                simulator.devices["ac_living"].turn_off()
                actions_executed.append("Turned OFF Living Room AC")

            report = "Sleep climate prepared: Bedroom AC at 23.5°C, fan on quiet mode, non-bedroom climate shut down."
            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=actions_executed,
                report=report
            )

        elif task.command == "PREPARE_AWAY_COMFORT":
            # Shut down all climate devices
            for dev_id, dev in simulator.devices.items():
                if dev.device_type in [DeviceType.AC, DeviceType.FAN] and dev.power_state == DevicePowerState.ON:
                    dev.turn_off()
                    actions_executed.append(f"Deactivated comfort device {dev.name}")

            report = f"Deactivated {len(actions_executed)} comfort devices for unoccupied home."
            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=actions_executed,
                report=report
            )

        elif task.command == "RESTORE_HOME_COMFORT":
            # Set living room AC to 24°C and lights
            ac_liv = simulator.devices.get("ac_living")
            if ac_liv and isinstance(ac_liv, AirConditioner):
                ac_liv.turn_on()
                ac_liv.set_target_temperature(24.0)
                actions_executed.append("Activated Living Room AC at 24.0°C")

            report = "Prepared living spaces for resident arrival with welcoming temperature (24.0°C)."
            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=actions_executed,
                report=report
            )

        return AgentTaskResult(
            task_id=task.task_id,
            agent_type=self.agent_type,
            success=False,
            report=f"Unrecognized comfort command: {task.command}"
        )

    def handle_incoming_message(self, msg: AgentMessage, simulator: Any) -> Optional[AgentMessage]:
        """Handles incoming peer-to-peer dialogues (e.g. Energy Agent negotiation)."""
        if msg.topic == "CLIMATE_ENERGY_TRADEOFF" and msg.msg_type == MessageType.NEGOTIATION_PROPOSAL:
            proposed_setpoint = float(msg.payload.get("proposed_setpoint", 24.0))
            current_temp = float(msg.payload.get("current_temp", 26.0))
            dev_id = msg.payload.get("device_id", "ac_bedroom")

            # Check if proposed setpoint preserves acceptable comfort
            if proposed_setpoint <= self.preferred_temp_max:
                # Accept proposal and adjust AC
                ac = simulator.devices.get(dev_id)
                if ac and isinstance(ac, AirConditioner):
                    ac.set_target_temperature(proposed_setpoint)

                reply_content = (
                    f"Indoor temperature is {current_temp:.1f}°C. "
                    f"Proposed thermostat setpoint ({proposed_setpoint:.1f}°C) is acceptable within "
                    f"resident comfort preferences ({self.preferred_temp_min}°C - {self.preferred_temp_max}°C). "
                    f"Thermostat adjusted to balance comfort and energy conservation."
                )
                self.latest_decision = f"Accepted Energy Agent compromise: {dev_id} set to {proposed_setpoint}°C."

                return self.send_message(
                    receiver=msg.sender,
                    msg_type=MessageType.NEGOTIATION_ACCEPT,
                    topic="CLIMATE_ENERGY_TRADEOFF",
                    content=reply_content,
                    payload={"agreed_setpoint": proposed_setpoint, "device_id": dev_id}
                )
            else:
                # Counter-propose at the maximum comfort threshold
                counter_setpoint = self.preferred_temp_max
                ac = simulator.devices.get(dev_id)
                if ac and isinstance(ac, AirConditioner):
                    ac.set_target_temperature(counter_setpoint)

                reply_content = (
                    f"Proposed setpoint of {proposed_setpoint:.1f}°C exceeds comfort maximum ({self.preferred_temp_max}°C). "
                    f"Counter-proposing {counter_setpoint:.1f}°C to preserve resident comfort."
                )
                self.latest_decision = f"Counter-proposed setpoint to Energy Agent: {counter_setpoint}°C."

                return self.send_message(
                    receiver=msg.sender,
                    msg_type=MessageType.NEGOTIATION_COUNTER,
                    topic="CLIMATE_ENERGY_TRADEOFF",
                    content=reply_content,
                    payload={"agreed_setpoint": counter_setpoint, "device_id": dev_id}
                )

        return None



