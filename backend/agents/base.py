"""Base agent class for HomeMind specialized AI agents."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime

from backend.simulation.models import HomeStateSnapshot
from backend.agents.schemas import (
    AgentType,
    AgentStatusEnum,
    AgentActionProposal,
    AgentAlert,
    AgentEvaluationResult
)
from backend.agents.orchestration import DelegationTask, AgentTaskResult
from backend.agents.communication import AgentMessage, MessageType, AgentMessageBus


class BaseAgent(ABC):
    """Abstract base class representing an autonomous specialized home agent."""

    def __init__(self, agent_type: AgentType, name: str, role: str, goal: str):
        self.agent_type = agent_type
        self.name = name
        self.role = role
        self.goal = goal
        self.status = AgentStatusEnum.IDLE
        self.current_task = "Initializing"
        self.latest_decision = "Awaiting initial perception"
        self.important_event = "System initialized"
        self.last_evaluated: Optional[datetime] = None
        self.bus: Optional[AgentMessageBus] = None

    def attach_bus(self, bus: AgentMessageBus) -> None:
        """Connects agent to shared inter-agent message bus."""
        self.bus = bus

    def send_message(
        self,
        receiver: AgentType,
        msg_type: MessageType,
        topic: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """Dispatches peer message to another agent through the message bus."""
        if not self.bus:
            return None
        msg = AgentMessage(
            sender=self.agent_type,
            receiver=receiver,
            msg_type=msg_type,
            topic=topic,
            content=content,
            payload=payload or {}
        )
        return self.bus.send(msg)

    def receive_messages(self, clear: bool = True) -> List[AgentMessage]:
        """Fetches pending messages from agent inbox."""
        if not self.bus:
            return []
        return self.bus.get_inbox(self.agent_type, clear=clear)

    def handle_incoming_message(self, msg: AgentMessage, simulator: Any) -> Optional[AgentMessage]:
        """Processes incoming peer message and optionally returns a reply message."""
        return None

    def get_display_status(self) -> Dict[str, Any]:
        """Returns format required by Section 9 for UI dashboard display."""
        return {
            "agent_type": self.agent_type.value,
            "name": self.name,
            "role": self.role,
            "goal": self.goal,
            "status": self.status.value,
            "current_task": self.current_task,
            "latest_decision": self.latest_decision,
            "important_event": self.important_event
        }

    @abstractmethod
    def evaluate(
        self,
        snapshot: HomeStateSnapshot,
        shared_context: Optional[Dict[str, Any]] = None
    ) -> AgentEvaluationResult:
        """Performs domain-specific analysis, reasoning, and recommendation generation."""
        pass

    @abstractmethod
    def handle_task(self, task: DelegationTask, simulator: Any) -> AgentTaskResult:
        """Executes a delegated task dispatched by the Home Manager."""
        pass


