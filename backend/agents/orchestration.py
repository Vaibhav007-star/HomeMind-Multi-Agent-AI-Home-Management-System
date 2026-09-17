"""Delegation models and workflow orchestration protocols for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from backend.agents.schemas import AgentType, ActionPriority
from backend.simulation.models import GlobalHomeState


class DelegationTask(BaseModel):
    """Specific task delegated by Home Manager to a specialized agent."""
    task_id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%H%M%S%f")[:10])
    recipient: AgentType
    command: str  # e.g. "DEACTIVATE_UNNECESSARY_LOADS", "ARM_AWAY_MONITORING"
    instruction: str  # Human-readable instruction
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: ActionPriority = ActionPriority.MEDIUM


class AgentTaskResult(BaseModel):
    """Structured report returned by a specialized agent upon completing a task."""
    task_id: str
    agent_type: AgentType
    success: bool = True
    actions_executed: List[str] = Field(default_factory=list)
    report: str
    data: Dict[str, Any] = Field(default_factory=dict)


class DelegationPlan(BaseModel):
    """Decomposition of high-level user intent into targeted agent tasks."""
    intent: str
    target_home_state: Optional[GlobalHomeState] = None
    tasks: List[DelegationTask] = Field(default_factory=list)
    rationale: str


class WorkflowExecutionResult(BaseModel):
    """Complete record of an orchestrated multi-agent workflow."""
    workflow_id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%H%M%S%f")[:10])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_prompt: str
    intent: str
    target_home_state: Optional[str] = None
    delegation_plan: DelegationPlan
    agent_results: Dict[str, AgentTaskResult] = Field(default_factory=dict)
    actions_applied: List[str] = Field(default_factory=list)
    final_response: str
    timeline: List[Dict[str, str]] = Field(default_factory=list)

