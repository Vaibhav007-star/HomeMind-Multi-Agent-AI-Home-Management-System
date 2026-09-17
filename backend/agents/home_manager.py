"""Home Manager Agent implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from backend.simulation.models import (
    HomeStateSnapshot,
    GlobalHomeState
)
from backend.agents.base import BaseAgent
from backend.agents.schemas import (
    AgentType,
    AgentStatusEnum,
    ActionPriority,
    AgentActionProposal,
    AgentAlert,
    AgentEvaluationResult,
    CoordinatorDecision
)
from backend.agents.orchestration import (
    DelegationTask,
    AgentTaskResult,
    DelegationPlan,
    WorkflowExecutionResult
)
from backend.agents.communication import (
    AgentMessage,
    MessageType,
    AgentMessageBus
)
from backend.memory import HomeStateMachine, SharedHomeMemory
from backend.agents.energy_agent import EnergyAgent
from backend.agents.comfort_agent import ComfortAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.resource_agent import ResourceAgent
from backend.agents.nlp_engine import NLPEngine


class HomeManagerAgent(BaseAgent):
    """Central coordinator orchestrating the 4 specialized agents, resolving conflicts,

    and synthesizing final multi-agent home decisions.
    """

    def __init__(self):
        super().__init__(
            agent_type=AgentType.HOME_MANAGER,
            name="Home Manager",
            role="Central Home Coordinator & Orchestrator",
            goal="Coordinate specialized agents, resolve conflicts, and maintain global home state"
        )
        # Instantiate the 4 specialized sub-agents
        self.energy_agent = EnergyAgent()
        self.comfort_agent = ComfortAgent()
        self.security_agent = SecurityAgent()
        self.resource_agent = ResourceAgent()

        self.sub_agents: Dict[AgentType, BaseAgent] = {
            AgentType.ENERGY: self.energy_agent,
            AgentType.COMFORT: self.comfort_agent,
            AgentType.SECURITY: self.security_agent,
            AgentType.RESOURCE: self.resource_agent
        }

        # Initialize shared peer-to-peer message bus and attach all agents (Phase 4)
        self.bus = AgentMessageBus()
        self.attach_bus(self.bus)
        for agent in self.sub_agents.values():
            agent.attach_bus(self.bus)

        # Initialize Shared State Machine and Contextual Memory (Phase 5 & 6)
        self.state_machine = HomeStateMachine(initial_state=GlobalHomeState.HOME)
        self.memory = SharedHomeMemory()

        # Initialize Natural Language Processing & LLM Engine (Phase 9)
        self.nlp = NLPEngine()

    def delegate_all(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> Dict[AgentType, AgentEvaluationResult]:
        """Delegates evaluation cycles to all specialized agents."""
        results: Dict[AgentType, AgentEvaluationResult] = {}
        for agent_type, agent in self.sub_agents.items():
            results[agent_type] = agent.evaluate(snapshot, shared_context)
        return results

    def resolve_conflicts(
        self,
        all_proposals: List[AgentActionProposal],
        snapshot: HomeStateSnapshot
    ) -> Tuple[List[AgentActionProposal], List[str]]:
        """Resolves competing goals between specialized agents.

        For example, Energy wants to turn off AC, while Comfort wants it on.
        Resolution principle:
          - If home is AWAY: Security & Energy take precedence.
          - If room is OCCUPIED in HOME mode: Comfort takes precedence.
          - CRITICAL priority actions always take precedence.
        """
        resolved_actions: List[AgentActionProposal] = []
        conflicts_noted: List[str] = []

        # Group proposals by target device/entity
        by_target: Dict[str, List[AgentActionProposal]] = {}
        for prop in all_proposals:
            by_target.setdefault(prop.target_id, []).append(prop)

        for target_id, props in by_target.items():
            if len(props) == 1:
                resolved_actions.append(props[0])
                continue

            # Multiple agents proposed actions on the same target
            # Check for conflict (e.g. TURN_OFF vs TURN_ON or SET_TEMP)
            actions = {p.action for p in props}
            if len(actions) > 1:
                # Genuine conflict detected
                energy_prop = next((p for p in props if p.agent_type == AgentType.ENERGY), None)
                comfort_prop = next((p for p in props if p.agent_type == AgentType.COMFORT), None)

                if energy_prop and comfort_prop:
                    # Energy vs Comfort conflict resolution
                    room_id = next((d.room_id for d in snapshot.devices.values() if d.id == target_id), "")
                    is_room_occupied = snapshot.rooms.get(room_id, None).occupied if room_id in snapshot.rooms else False

                    if snapshot.global_home_state == GlobalHomeState.AWAY or not is_room_occupied:
                        # Favor Energy when room is unoccupied or home is AWAY
                        resolved_actions.append(energy_prop)
                        conflicts_noted.append(
                            f"Conflict on {target_id}: Energy Agent proposal selected ({energy_prop.action}) "
                            f"over Comfort Agent because room '{room_id}' is unoccupied or home is AWAY."
                        )
                    else:
                        # Favor Comfort when room is actively occupied by resident
                        resolved_actions.append(comfort_prop)
                        conflicts_noted.append(
                            f"Conflict on {target_id}: Comfort Agent proposal selected ({comfort_prop.action}) "
                            f"over Energy Agent because room '{room_id}' is currently occupied."
                        )
                else:
                    # Sort by priority tier
                    priority_order = {
                        ActionPriority.CRITICAL: 4,
                        ActionPriority.HIGH: 3,
                        ActionPriority.MEDIUM: 2,
                        ActionPriority.LOW: 1
                    }
                    sorted_props = sorted(props, key=lambda p: priority_order.get(p.priority, 0), reverse=True)
                    winner = sorted_props[0]
                    resolved_actions.append(winner)
                    conflicts_noted.append(f"Conflict on {target_id} resolved by priority tier: {winner.agent_type.value} won.")
            else:
                # Agents agreed on action
                resolved_actions.append(props[0])

        return resolved_actions, conflicts_noted

    def evaluate(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> AgentEvaluationResult:
        """Home Manager evaluation cycle."""
        self.status = AgentStatusEnum.COORDINATING
        self.current_task = "Coordinating specialized agents and synthesizing home state"

        # 1. Delegate to specialized agents
        sub_results = self.delegate_all(snapshot, shared_context)

        # 2. Collect all recommendations and alerts
        all_recommendations: List[AgentActionProposal] = []
        all_alerts: List[AgentAlert] = []
        for res in sub_results.values():
            all_recommendations.extend(res.recommendations)
            all_alerts.extend(res.alerts)

        # 3. Detect multi-agent cross-domain correlation (Section 3, Example 2)
        # Abnormal water usage + unoccupied home = Leak alert
        water_alert = next((a for a in sub_results[AgentType.RESOURCE].alerts if "Water" in a.title), None)
        is_unoccupied = all(not r.occupied for r in snapshot.rooms.values())

        if water_alert and (is_unoccupied or snapshot.global_home_state == GlobalHomeState.AWAY):
            correlated_alert = AgentAlert(
                agent_type=self.agent_type,
                title="Cross-Agent Correlated Incident: Possible Water Leak",
                severity="CRITICAL",
                description="Resource Agent reports abnormal water flow while Security Agent confirms zero resident activity. High probability of plumbing breach.",
                evidence=[
                    f"Resource Agent finding: Water outflow {snapshot.water_system.flow_rate_lpm:.1f} L/min",
                    f"Security Agent finding: 0 motion detections across all rooms",
                    f"Home State: {snapshot.global_home_state.value}"
                ],
                recommended_action="Recommend emergency shutoff valve closure."
            )
            all_alerts.insert(0, correlated_alert)
            self.important_event = "CRITICAL: Correlated water leak detected"

        # 4. Resolve conflicts
        approved_actions, conflicts = self.resolve_conflicts(all_recommendations, snapshot)

        # 5. Formulate final summary
        summary = (
            f"Coordinated 4 specialized agents. "
            f"Approved {len(approved_actions)} actions ({len(conflicts)} conflicts resolved), {len(all_alerts)} active alerts."
        )
        self.latest_decision = f"Home state {snapshot.global_home_state.value}: {len(approved_actions)} actions approved."

        return AgentEvaluationResult(
            agent_type=self.agent_type,
            agent_name=self.name,
            status=self.status,
            current_task=self.current_task,
            summary=summary,
            recommendations=approved_actions,
            alerts=all_alerts,
            metrics={
                "sub_agents_count": 4,
                "approved_actions_count": len(approved_actions),
                "conflicts_resolved_count": len(conflicts),
                "total_alerts_count": len(all_alerts)
            }
        )

    def coordinate_cycle(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> CoordinatorDecision:
        """Executes full multi-agent cycle and produces final CoordinatorDecision."""
        eval_result = self.evaluate(snapshot, shared_context)
        explanation = (
            f"Home is in {snapshot.global_home_state.value} mode. "
            f"Home Manager coordinated 4 domain agents, resulting in {len(eval_result.recommendations)} approved actions "
            f"and {len(eval_result.alerts)} alerts."
        )
        return CoordinatorDecision(
            home_state=snapshot.global_home_state.value,
            summary=eval_result.summary,
            approved_actions=eval_result.recommendations,
            conflicts_resolved=[],
            active_alerts=eval_result.alerts,
            explanation=explanation
        )

    def parse_intent(self, user_prompt: str) -> DelegationPlan:
        """Deconstructs high-level user prompt into specialized domain tasks using the NLP Engine."""
        return self.nlp.understand_intent(
            user_prompt=user_prompt,
            current_state=self.state_machine.current_state
        )

    def execute_workflow(self, user_prompt: str, simulator: Any) -> WorkflowExecutionResult:
        """Coordinates the end-to-end multi-agent workflow for a user request."""
        time_str = simulator.sim_time.strftime("%H:%M")
        timeline: List[Dict[str, str]] = []

        # 1. Parse intent and formulate delegation plan
        plan = self.parse_intent(user_prompt)
        timeline.append({"time": time_str, "source": "User", "event": f"Instruction received: '{user_prompt}'"})
        timeline.append({
            "time": time_str,
            "source": "Home Manager",
            "event": f"Intent parsed: [{plan.intent}]. Delegating {len(plan.tasks)} domain tasks to specialized agents."
        })

        # Contextual habit recognition (Section 5 Example)
        if plan.intent == "LEAVING_HOME":
            is_habit, habit_ctx = self.memory.get_departure_context(simulator.sim_time)
            timeline.append({
                "time": time_str,
                "source": "Contextual Memory",
                "event": habit_ctx
            })

        agent_results: Dict[str, AgentTaskResult] = {}
        all_actions: List[str] = []

        # 2. Dispatch delegated tasks to specialized agents
        for task in plan.tasks:
            agent = self.sub_agents.get(task.recipient)
            if agent:
                # Log task assignment message on the inter-agent bus
                self.send_message(
                    receiver=task.recipient,
                    msg_type=MessageType.INFORM,
                    topic=task.command,
                    content=task.instruction,
                    payload=task.parameters
                )
                res = agent.handle_task(task, simulator)
                agent_results[task.recipient.value] = res
                all_actions.extend(res.actions_executed)
                # Log agent response message back on bus
                if self.bus:
                    self.bus.send(AgentMessage(
                        sender=task.recipient,
                        receiver=AgentType.HOME_MANAGER,
                        msg_type=MessageType.RESPONSE,
                        topic=task.command,
                        content=res.report,
                        payload=res.data
                    ))
                timeline.append({
                    "time": time_str,
                    "source": agent.name,
                    "event": f"Executed [{task.command}]: {res.report}"
                })

        # 3. Update global home state if requested by plan via State Machine
        if plan.target_home_state:
            success, tr_record = self.state_machine.transition_to(
                target_state=plan.target_home_state,
                reason=plan.rationale,
                initiator="UserWorkflow"
            )
            simulator.set_global_home_state(plan.target_home_state)
            tr_id = tr_record.transition_id if tr_record else "direct"
            timeline.append({
                "time": time_str,
                "source": "State Machine",
                "event": f"Transitioned Global Home State to {plan.target_home_state.value} (ID: {tr_id})."
            })

        # 4. Formulate comprehensive final response for resident
        final_response = self.nlp.generate_natural_response(
            intent=plan.intent,
            user_prompt=user_prompt,
            rationale=plan.rationale,
            target_state=plan.target_home_state,
            agent_results=agent_results
        )
        if plan.target_home_state:
            policy = self.state_machine.get_active_policy()
            final_response += f"\n\n**Global Home State is now: {plan.target_home_state.value}** ({policy.description})"

        self.latest_decision = f"Completed {plan.intent} workflow ({len(all_actions)} actions applied)."

        # Record decision into contextual memory archive
        self.memory.record_decision(
            CoordinatorDecision(
                home_state=self.state_machine.current_state.value,
                summary=f"Workflow '{plan.intent}' executed: {len(all_actions)} actions applied.",
                approved_actions=[],
                active_alerts=[],
                explanation=final_response
            )
        )

        return WorkflowExecutionResult(
            user_prompt=user_prompt,
            intent=plan.intent,
            target_home_state=plan.target_home_state.value if plan.target_home_state else None,
            delegation_plan=plan,
            agent_results=agent_results,
            actions_applied=all_actions,
            final_response=final_response,
            timeline=timeline
        )

    def run_climate_energy_negotiation(
        self,
        target_ac_id: str,
        proposed_setpoint: float,
        simulator: Any
    ) -> Optional[AgentMessage]:
        """Orchestrates direct horizontal Energy <-> Comfort negotiation (Section 3 Example 1)."""
        room_id = simulator.devices[target_ac_id].room_id if target_ac_id in simulator.devices else "bedroom"
        current_temp = simulator.rooms[room_id].temperature_celsius if room_id in simulator.rooms else 27.0

        # Energy Agent negotiates directly with Comfort Agent
        reply = self.energy_agent.propose_climate_tradeoff(
            target_ac_id=target_ac_id,
            proposed_setpoint=proposed_setpoint,
            current_temp=current_temp,
            comfort_agent=self.comfort_agent,
            simulator=simulator
        )

        # Home Manager logs resolution to bus
        if reply:
            self.send_message(
                receiver=AgentType.ENERGY,
                msg_type=MessageType.INFORM,
                topic="NEGOTIATION_LOGGED",
                content=f"Home Manager recorded Energy-Comfort consensus on {target_ac_id}."
            )
        return reply

    def run_ac_setpoint_negotiation(
        self,
        device_id: str = "ac_living",
        initial_comfort_target: float = 22.0,
        energy_preferred_target: float = 25.5,
        simulator: Optional[Any] = None
    ) -> Tuple[float, List[AgentMessage]]:
        """Coordinates direct inter-agent climate setpoint negotiation (Section 3 & Phase 12)."""
        from backend.simulation.simulator import HomeSimulator
        sim = simulator if simulator is not None else HomeSimulator()
        if device_id in sim.devices:
            sim.set_ac_target(device_id, initial_comfort_target)

        # Propose a balanced compromise setpoint (midpoint between comfort and energy preference)
        proposed_compromise = round((initial_comfort_target + energy_preferred_target) / 2.0 * 2) / 2.0
        reply = self.run_climate_energy_negotiation(
            target_ac_id=device_id,
            proposed_setpoint=proposed_compromise,
            simulator=sim
        )
        rounds = self.bus.get_conversation(AgentType.ENERGY, AgentType.COMFORT)
        dev = sim.devices.get(device_id)
        final_temp = float(dev.attributes.get("target_temp_celsius", proposed_compromise)) if dev else proposed_compromise
        return final_temp, rounds

    def run_water_security_verification(self, simulator: Any) -> Optional[AgentMessage]:
        """Orchestrates direct Resource <-> Security cross-inquiry (Section 3 Example 2)."""
        reply = self.resource_agent.verify_water_anomaly_with_security(
            security_agent=self.security_agent,
            simulator=simulator
        )
        if reply:
            # Resource informs Home Manager
            self.resource_agent.send_message(
                receiver=AgentType.HOME_MANAGER,
                msg_type=MessageType.ALERT_SHARE,
                topic="CORRELATED_LEAKAGE_CONFIRMED",
                content="Resource Agent confirmed water outflow while Security Agent verified zero resident presence."
            )
        return reply

    def get_communication_matrix(self) -> Dict[str, Any]:
        """Returns Section 11 visual communication view data."""
        return self.bus.get_communication_matrix()

    def get_memory_summary(self) -> Dict[str, Any]:
        """Returns structured memory profile and active state machine policy."""
        return {
            "current_state": self.state_machine.current_state.value,
            "active_policy": self.state_machine.get_active_policy().model_dump(),
            "transition_count": len(self.state_machine.transition_history),
            "memory_summary": self.memory.get_summary()
        }

    def handle_task(self, task: DelegationTask, simulator: Any) -> AgentTaskResult:
        """Self task execution handler."""
        return AgentTaskResult(
            task_id=task.task_id,
            agent_type=self.agent_type,
            success=True,
            report="Home Manager delegating tasks."
        )




