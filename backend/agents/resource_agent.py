"""Resource Management Agent implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional, Any

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
    AgentEvaluationResult
)
from backend.agents.orchestration import DelegationTask, AgentTaskResult
from backend.agents.communication import AgentMessage, MessageType


class ResourceAgent(BaseAgent):
    """Specialized Agent responsible for household resources, water reserves, inventory, and maintenance."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.RESOURCE,
            name="Resource Agent",
            role="Resource & Maintenance Management",
            goal="Track water reserves, supplies, maintenance health, and detect consumption abnormalities"
        )
        self.water_low_threshold_percent = 25.0
        self.water_critical_threshold_percent = 15.0

        # Household grocery and supply inventory tracking
        self.inventory: Dict[str, Dict[str, Any]] = {
            "drinking_water": {"current": 2, "unit": "bottles", "min_threshold": 3, "category": "essentials"},
            "milk": {"current": 1, "unit": "carton", "min_threshold": 2, "category": "dairy"},
            "eggs": {"current": 4, "unit": "pieces", "min_threshold": 6, "category": "produce"},
            "detergent": {"current": 0.3, "unit": "kg", "min_threshold": 0.5, "category": "household"},
            "ac_filter_health": {"current": 88, "unit": "%", "min_threshold": 20, "category": "maintenance"},
        }

    def evaluate(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> AgentEvaluationResult:
        self.status = AgentStatusEnum.ANALYZING
        self.current_task = "Tracking water reservoir, plumbing flow, and household supplies"
        recommendations: List[AgentActionProposal] = []
        alerts: List[AgentAlert] = []

        water = snapshot.water_system
        home_state = snapshot.global_home_state

        # 1. Abnormal Water Flow / Leak Detection
        # Flow rate > 0 when home is AWAY or leak rate flagged
        if water.flow_rate_lpm > 0.5:
            if home_state == GlobalHomeState.AWAY:
                alerts.append(AgentAlert(
                    agent_type=self.agent_type,
                    title="Abnormal Water Outflow Detected",
                    severity="WARNING",
                    description=f"Plumbing flow sensor registers {water.flow_rate_lpm:.1f} L/min while home is unoccupied.",
                    evidence=[
                        f"Active water outflow: {water.flow_rate_lpm:.2f} L/min",
                        f"Water tank level: {water.current_water_liters:.1f} L ({water.water_level_percent:.1f}%)",
                        f"Home state: {home_state.value}",
                        "Resident occupancy: 0 across all rooms"
                    ],
                    recommended_action="Inspect plumbing fixtures for leaks or shut off main supply."
                ))
                self.important_event = f"Abnormal water flow: {water.flow_rate_lpm:.1f} L/min"
                self.status = AgentStatusEnum.ALERTING

        # 2. Water Tank Depletion Check
        if water.water_level_percent <= self.water_critical_threshold_percent:
            alerts.append(AgentAlert(
                agent_type=self.agent_type,
                title="Critical Water Tank Reserve",
                severity="CRITICAL",
                description=f"Overhead tank is critically low at {water.water_level_percent:.1f}% ({water.current_water_liters:.0f} L).",
                evidence=[
                    f"Tank percentage: {water.water_level_percent:.1f}%",
                    f"Critical threshold: {self.water_critical_threshold_percent}%"
                ],
                recommended_action="Activate water pump immediately."
            ))
            # Propose turning on pump
            recommendations.append(AgentActionProposal(
                agent_type=self.agent_type,
                target_type="device",
                target_id="water_pump",
                action="TURN_ON",
                priority=ActionPriority.CRITICAL,
                reason="Refill overhead water tank to prevent complete runout.",
                explainable_evidence=[f"Tank level at {water.water_level_percent:.1f}% <= {self.water_critical_threshold_percent}%"]
            ))
        elif water.water_level_percent <= self.water_low_threshold_percent and not water.pump_active:
            recommendations.append(AgentActionProposal(
                agent_type=self.agent_type,
                target_type="device",
                target_id="water_pump",
                action="TURN_ON",
                priority=ActionPriority.MEDIUM,
                reason="Overhead tank is below 25%. Schedule refill.",
                explainable_evidence=[f"Tank level at {water.water_level_percent:.1f}%"]
            ))

        # 3. Inventory & Grocery Restocking Check
        low_items = []
        for item_name, data in self.inventory.items():
            if data["current"] < data["min_threshold"]:
                low_items.append(f"{item_name.replace('_', ' ').title()} ({data['current']} {data['unit']})")

        if low_items:
            recommendations.append(AgentActionProposal(
                agent_type=self.agent_type,
                target_type="inventory",
                target_id="grocery_list",
                action="RESTOCK_ITEMS",
                parameters={"items": low_items},
                priority=ActionPriority.LOW,
                reason=f"Depleted household supplies need restocking: {', '.join(low_items)}.",
                explainable_evidence=[f"Items below minimum threshold: {', '.join(low_items)}"]
            ))

        # Summary & Decision
        if alerts:
            self.latest_decision = f"ALERT: {alerts[0].title}"
        elif recommendations:
            self.latest_decision = f"Generated {len(recommendations)} resource & refill recommendations."
        else:
            self.latest_decision = f"Resources stable. Tank at {water.water_level_percent:.1f}%."

        summary = (
            f"Water Tank: {water.current_water_liters:.0f}L ({water.water_level_percent:.1f}%), Flow: {water.flow_rate_lpm:.1f} L/min. "
            f"Alerts: {len(alerts)}, Restock items: {len(low_items)}."
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
                "tank_liters": water.current_water_liters,
                "tank_percent": water.water_level_percent,
                "flow_rate_lpm": water.flow_rate_lpm,
                "pump_active": water.pump_active,
                "low_inventory_count": len(low_items)
            }
        )

    def handle_task(self, task: DelegationTask, simulator: Any) -> AgentTaskResult:
        """Executes task delegated by Home Manager."""
        self.status = AgentStatusEnum.ANALYZING
        self.current_task = f"Executing delegated task: {task.command}"

        if task.command in ["CHECK_RESOURCES", "CHECK_WATER_SYSTEM"]:
            water = simulator.env
            tank_pct = (water.current_water_liters / water.water_tank_capacity_liters) * 100.0
            leak = water.simulated_leak_rate_lpm
            flow = water.fixture_usage_lpm + leak

            report = (
                f"Resource Audit: Water tank at {water.current_water_liters:.0f} L ({tank_pct:.1f}%). "
                f"Active outflow: {flow:.1f} L/min."
            )
            if leak > 0:
                report += f" WARNING: Unscheduled leak of {leak:.1f} L/min detected!"

            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=[],
                report=report,
                data={
                    "tank_liters": water.current_water_liters,
                    "tank_percent": round(tank_pct, 1),
                    "flow_lpm": round(flow, 1),
                    "leak_detected": leak > 0
                }
            )

        elif task.command in ["INVENTORY_AUDIT", "CHECK_SUPPLIES"]:
            needed_items = []
            for item_name, info in self.inventory.items():
                if info["current"] < info["min_threshold"]:
                    needed_items.append(f"{item_name.replace('_', ' ').title()} (have {info['current']} {info['unit']}, min {info['min_threshold']})")

            if needed_items:
                report = f"Inventory Audit: {len(needed_items)} items need restocking: {', '.join(needed_items)}."
            else:
                report = "Inventory Audit: All groceries and household supplies are adequately stocked."

            self.latest_decision = report

            return AgentTaskResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                actions_executed=[],
                report=report,
                data={"restock_items": needed_items, "items_needed_count": len(needed_items)}
            )

        return AgentTaskResult(
            task_id=task.task_id,
            agent_type=self.agent_type,
            success=False,
            report=f"Unrecognized resource command: {task.command}"
        )

    def verify_water_anomaly_with_security(
        self,
        security_agent: BaseAgent,
        simulator: Any
    ) -> Optional[AgentMessage]:
        """Cross-agent collaboration with Security Agent (Section 3 Example 2).

        Queries Security Agent to confirm whether resident activity correlates with water outflow.
        """
        flow = simulator.env.fixture_usage_lpm + simulator.env.simulated_leak_rate_lpm
        if flow <= 0.0:
            return None

        query_content = f"Water consumption is unusually high ({flow:.1f} L/min). Can you verify resident activity or motion?"
        query = self.send_message(
            receiver=AgentType.SECURITY,
            msg_type=MessageType.QUERY,
            topic="OCCUPANCY_VERIFICATION",
            content=query_content,
            payload={"flow_rate_lpm": flow}
        )

        if query:
            self.important_event = f"Queried Security Agent regarding {flow:.1f} L/min water outflow"
            response = security_agent.handle_incoming_message(query, simulator)
            return response
        return None



