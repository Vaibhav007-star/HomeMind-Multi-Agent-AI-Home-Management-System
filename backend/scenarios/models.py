"""Data models for HomeMind demonstration scenarios."""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from backend.agents.schemas import AgentAlert


class ScenarioStep(BaseModel):
    """Discrete step within a multi-agent scenario execution."""
    step_index: int
    time_str: str
    actor: str
    action_type: str  # "ANALYSIS", "ACTION", "DIALOGUE", "STATE_CHANGE", "ALERT"
    description: str
    evidence: List[str] = Field(default_factory=list)


class ScenarioReport(BaseModel):
    """Consolidated record of a demonstration scenario execution."""
    scenario_id: str
    title: str
    description: str
    sim_time_start: str
    sim_time_end: str
    initial_state: str
    final_state: str
    steps: List[ScenarioStep] = Field(default_factory=list)
    agent_summaries: Dict[str, str] = Field(default_factory=dict)
    alerts: List[AgentAlert] = Field(default_factory=list)
    explainability_summary: str

