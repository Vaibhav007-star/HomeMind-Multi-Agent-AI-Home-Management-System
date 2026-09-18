"""Security Agent implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional, Any

from backend.simulation.models import (
    HomeStateSnapshot,
    GlobalHomeState,
    DoorState,
    LockState
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


class SecurityAgent(BaseAgent):
    """Specialized Agent responsible for perimeter defense, access monitoring, and intruder detection."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.SECURITY,
            name="Security Agent",
            role="Perimeter Defense & Access Monitoring",
            goal="Protect the home and detect unauthorized or abnormal activity"
        )

    def evaluate(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> AgentEvaluationResult:
        self.status = AgentStatusEnum.MONITORING
        self.current_task = "Evaluating perimeter integrity & activity classification"
        recommendations: List[AgentActionProposal] = []
        alerts: List[AgentAlert] = []

        home_state = snapshot.global_home_state
        sec_state = snapshot.security_system
        is_away = (home_state == GlobalHomeState.AWAY) or sec_state.away_mode_armed

        # 1. Front door open while AWAY
        if is_away and sec_state.entrance_door_state == DoorState.OPEN:
            alerts.append(AgentAlert(
                agent_type=self.agent_type,
                title="Unauthorized Perimeter Breach (Front Door)",
                severity="CRITICAL",
                description="Main entrance door was opened while home is in AWAY state with no recognized resident.",
                evidence=[
                    "Home state is set to AWAY",
                    "Front door contact sensor state: OPEN",
                    "Away mode armed: True"
                ],
                recommended_action="Notify residents immediately and verify home status."
            ))
            self.status = AgentStatusEnum.ALERTING
            self.important_event = "CRITICAL: Front door opened in AWAY mode"

        # 2. Motion detected while AWAY
        active_motion_rooms = [r.room_name for r in snapshot.rooms.values() if r.motion_detected]
        if is_away and active_motion_rooms:
            alerts.append(AgentAlert(
                agent_type=self.agent_type,
                title="Unexpected Motion in Vacant Home",
                severity="CRITICAL",
                description=f"Motion detected in {', '.join(active_motion_rooms)} while home is marked AWAY.",
                evidence=[
                    f"Motion detected in: {', '.join(active_motion_rooms)}",
                    "Home state is AWAY",
                    "Expected resident occupancy: 0"
                ],
                recommended_action="Inspect camera feed and confirm resident whereabouts."
            ))
            self.status = AgentStatusEnum.ALERTING

        # 3. Unlocked door when leaving / in AWAY mode
        if is_away and sec_state.entrance_lock_state == LockState.UNLOCKED:
            recommendations.append(AgentActionProposal(
                agent_type=self.agent_type,
                target_type="device",
                target_id="lock_entrance",
                action="LOCK",
                priority=ActionPriority.HIGH,
                reason="Front door smart lock is UNLOCKED while home is in AWAY state.",
                explainable_evidence=[
                    "Home is in AWAY mode",
                    "Smart lock status: UNLOCKED"
                ]
            ))

        # 4. SLEEP Mode perimeter check
        if home_state == GlobalHomeState.SLEEP and sec_state.entrance_lock_state == LockState.UNLOCKED:
            recommendations.append(AgentActionProposal(
                agent_type=self.agent_type,
                target_type="device",
                target_id="lock_entrance",
                action="LOCK",
                priority=ActionPriority.HIGH,
                reason="Secure front door lock for overnight SLEEP mode.",
                explainable_evidence=[
                    "Home state is SLEEP",
                    "Smart lock status: UNLOCKED"
                ]
            ))

        # Overall Status
        if alerts:
            self.latest_decision = f"ACTIVE SECURITY ALERT: {alerts[0].title}"
        elif recommendations:
            self.latest_decision = f"Proposed {len(recommendations)} perimeter security actions."
        else:
            self.latest_decision = f"Perimeter secure. Door {sec_state.entrance_door_state.value}, Lock {sec_state.entrance_lock_state.value}."

        summary = (
            f"Perimeter: Door {sec_state.entrance_door_state.value}, Lock {sec_state.entrance_lock_state.value}. "
            f"Alerts: {len(alerts)}, Recommendations: {len(recommendations)}."
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
                "door_state": sec_state.entrance_door_state.value,
                "lock_state": sec_state.entrance_lock_state.value,
                "away_armed": sec_state.away_mode_armed,
                "active_alerts_count": len(alerts),
                "motion_rooms": active_motion_rooms
            }
        )

    def handle_task(self, task: DelegationTask, simulator: Any) -> AgentTaskResult:
        """Executes task delegated by Home Manager."""
        self.status = AgentStatusEnum.MONITORING
        self.current_task = f"Executing delegated task: {task.command}"
        actions_executed: List[str] = []

        if task.command == "ARM_AWAY_MONITORING":
            # Lock front door
            simulator.set_lock_state(True)
            actions_executed.append("Front door smart lock engaged (LOCKED)")

            # Ensure door closed
            simulator.set_door_state(False)

            # Arm away mode
            simulator.env.away_mode_armed = True
            actions_executed.append("Away Mode perimeter monitoring armed")

            # Reset occupancy
            for r_id in simulator.rooms:
                simulator.set_occupancy(r_id, False)

            report = "Perimeter secured: Front door locked, away sensors armed, room occupancy reset to vacant."
            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=actions_executed,
                report=report,
                data={"lock_state": "LOCKED", "away_armed": True}
            )

        elif task.command == "SECURE_FOR_SLEEP":
            simulator.set_lock_state(True)
            actions_executed.append("Front door locked for overnight security")
            report = "Overnight perimeter secured: Front door locked, night intrusion monitoring active."
            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=actions_executed,
                report=report
            )

        elif task.command == "AUDIT_HOME_SECURITY":
            door = simulator.env.entrance_door_state.value
            lock = simulator.env.entrance_lock_state.value
            armed = simulator.env.away_mode_armed
            motion_rooms = [r.room_name for r in simulator.rooms.values() if r.motion_detected]

            report = f"Security Audit: Front Door is {door}, Lock is {lock}, Away Armed: {armed}."
            if motion_rooms:
                report += f" Motion detected in: {', '.join(motion_rooms)}."
            else:
                report += " No unexpected motion detected."

            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=[],
                report=report,
                data={"door": door, "lock": lock, "armed": armed, "motion_rooms": motion_rooms}
            )

        elif task.command == "DISARM_TO_HOME":
            simulator.env.away_mode_armed = False
            simulator.set_lock_state(False)
            simulator.set_occupancy("entrance", True)
            simulator.set_occupancy("living_room", True)
            actions_executed.append("Disarmed Away Mode to standard Home Mode")
            actions_executed.append("Unlocked front entrance smart lock for resident entry")
            actions_executed.append("Registered resident arrival: Entrance and Living Room Occupied")
            report = "Perimeter monitoring set to standard daytime HOME mode. Front door unlocked and resident arrival registered in Living Room."
            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=actions_executed,
                report=report,
                data={"lock_state": "UNLOCKED", "away_armed": False, "occupied_rooms": ["Entrance", "Living Room"]}
            )

        return AgentTaskResult(
            task_id=task.task_id,
            agent_type=self.agent_type,
            success=False,
            report=f"Unrecognized security command: {task.command}"
        )

    def handle_incoming_message(self, msg: AgentMessage, simulator: Any) -> Optional[AgentMessage]:
        """Handles incoming peer-to-peer dialogues (e.g. Resource Agent inquiry)."""
        if msg.topic == "OCCUPANCY_VERIFICATION" and msg.msg_type == MessageType.QUERY:
            motion_rooms = [r.room_name for r in simulator.rooms.values() if r.motion_detected or r.occupied]
            is_unoccupied = len(motion_rooms) == 0

            if is_unoccupied:
                reply_content = (
                    "No resident activity has been detected. All 5 rooms report zero occupancy, "
                    "motion sensors are clear, and perimeter door is secure."
                )
            else:
                reply_content = (
                    f"Resident presence detected in: {', '.join(motion_rooms)}. "
                    "Water consumption likely corresponds to resident activity."
                )

            self.latest_decision = f"Responded to Resource Agent query: {'Unoccupied' if is_unoccupied else 'Occupied'}."

            return self.send_message(
                receiver=msg.sender,
                msg_type=MessageType.RESPONSE,
                topic="OCCUPANCY_VERIFICATION",
                content=reply_content,
                payload={"is_unoccupied": is_unoccupied, "motion_rooms": motion_rooms}
            )

        return None



