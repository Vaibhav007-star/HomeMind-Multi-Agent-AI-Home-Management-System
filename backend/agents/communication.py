"""Agent-to-Agent Communication Bus and Protocols for HomeMind."""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from backend.agents.schemas import AgentType


class MessageType(str, Enum):
    """Types of inter-agent messages."""
    INFORM = "INFORM"
    QUERY = "QUERY"
    RESPONSE = "RESPONSE"
    NEGOTIATION_PROPOSAL = "NEGOTIATION_PROPOSAL"
    NEGOTIATION_COUNTER = "NEGOTIATION_COUNTER"
    NEGOTIATION_ACCEPT = "NEGOTIATION_ACCEPT"
    ALERT_SHARE = "ALERT_SHARE"


class AgentMessage(BaseModel):
    """Structured message passed directly between two agents."""
    message_id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%H%M%S%f")[:10])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sender: AgentType
    receiver: AgentType
    msg_type: MessageType
    topic: str  # e.g., "CLIMATE_ENERGY_TRADEOFF", "OCCUPANCY_VERIFICATION"
    content: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentMessageBus:
    """Central peer-to-peer messaging backbone connecting all five agents."""

    def __init__(self):
        self.messages: List[AgentMessage] = []
        self._inboxes: Dict[AgentType, List[AgentMessage]] = {
            agent_t: [] for agent_t in AgentType
        }

    def send(self, message: AgentMessage) -> AgentMessage:
        """Publishes a message to the recipient's inbox and logs to global history."""
        self.messages.append(message)
        if message.receiver in self._inboxes:
            self._inboxes[message.receiver].append(message)
        return message

    def get_inbox(self, agent: AgentType, clear: bool = False) -> List[AgentMessage]:
        """Retrieves messages waiting in an agent's inbox."""
        msgs = list(self._inboxes.get(agent, []))
        if clear:
            self._inboxes[agent].clear()
        return msgs

    def get_conversation(self, agent1: AgentType, agent2: AgentType) -> List[AgentMessage]:
        """Retrieves the dialogue history exchanged between two specific agents."""
        return [
            m for m in self.messages
            if (m.sender == agent1 and m.receiver == agent2) or (m.sender == agent2 and m.receiver == agent1)
        ]

    def get_all_messages(self) -> List[AgentMessage]:
        """Returns entire inter-agent message history."""
        return list(self.messages)

    def get_communication_matrix(self) -> Dict[str, Any]:
        """Generates communication view data matching Section 11 of the specification.

        Example:
          Home Manager -> Energy Agent
          Energy Agent <-> Comfort Agent
          Resource Agent -> Home Manager
          Security Agent -> Home Manager
        """
        edge_counts: Dict[str, Dict[str, Any]] = {}
        for m in self.messages:
            key = f"{m.sender.value}->{m.receiver.value}"
            if key not in edge_counts:
                edge_counts[key] = {
                    "source": m.sender.value,
                    "target": m.receiver.value,
                    "count": 0,
                    "last_topic": m.topic,
                    "last_message": m.content
                }
            edge_counts[key]["count"] += 1
            edge_counts[key]["last_message"] = m.content

        nodes = [
            {"id": a.value, "label": a.value.replace("_", " ").title()}
            for a in AgentType
        ]

        return {
            "nodes": nodes,
            "edges": list(edge_counts.values()),
            "total_messages": len(self.messages)
        }

