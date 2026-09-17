"""Data models for explainable decisions and safety classifications (Phase 10).

Adheres to:
- Section 13 (Explainable Decisions: Concise decision explanations based on observable inputs and actions)
- Section 16 (Safety: Non-destructive actions, recommendations, safety tiers)
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from backend.agents.schemas import AgentType, ActionPriority


class SafetyTier(str, Enum):
    """Safety classification for agent actions per Section 16."""
    SAFE_AUTONOMOUS = "SAFE_AUTONOMOUS"  # Low-risk routine operations (e.g. dimming lights, adjusting AC within bounds)
    RECOMMENDATION_ONLY = "RECOMMENDATION_ONLY"  # Suggested optimizations (e.g. grocery list, peak hour shifting)
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"  # Potentially disruptive actions (e.g. closing main water shutoff valve)


class DecisionExplanation(BaseModel):
    """Structured, human-explainable record for an agent decision or alert (Section 13)."""
    explanation_id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:17])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    time_str: str = ""
    title: str
    decision_type: str  # "ALERT", "ACTION", "STATE_TRANSITION", "CONFLICT_RESOLUTION", "DELEGATION"
    origin_agent: AgentType
    participating_agents: List[AgentType] = Field(default_factory=list)
    summary: str
    why_points: List[str] = Field(default_factory=list)  # Concise observable reasons answering "Why?"
    observable_inputs: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: Optional[str] = None
    safety_tier: SafetyTier = SafetyTier.SAFE_AUTONOMOUS
    user_confirmed: bool = False

