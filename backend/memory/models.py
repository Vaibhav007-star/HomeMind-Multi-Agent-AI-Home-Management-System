"""Data models for HomeMind shared state machine and structured contextual memory."""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from backend.simulation.models import GlobalHomeState


class ResidentProfile(BaseModel):
    """Resident preference and schedule habits."""
    resident_id: str = "resident_1"
    name: str = "Alex Morgan"
    role: str = "Primary Resident"
    preferred_temp_min: float = 22.0
    preferred_temp_max: float = 25.5
    preferred_sleep_temp: float = 23.5
    typical_wake_time: str = "07:00"
    typical_departure_time: str = "08:30"
    typical_return_time: str = "17:30"
    typical_sleep_time: str = "23:00"


class ScheduleHabit(BaseModel):
    """Recurring scheduled habit or window."""
    habit_id: str
    name: str
    window_start: str  # e.g., "08:15"
    window_end: str    # e.g., "08:45"
    target_state: GlobalHomeState
    description: str


class StatePolicy(BaseModel):
    """Operational policies dictating agent behavior under a specific home state."""
    state: GlobalHomeState
    max_discretionary_watts: float
    security_armed: bool
    strict_perimeter: bool
    allow_vacant_room_cooling: bool
    lock_doors_required: bool
    dim_lights_required: bool
    description: str


class StateTransitionRecord(BaseModel):
    """Logged audit trail of a global state transition."""
    transition_id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%H%M%S%f")[:10])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    from_state: GlobalHomeState
    to_state: GlobalHomeState
    trigger_reason: str
    initiator: str  # "User", "HomeManagerAgent", "SecurityRule"

