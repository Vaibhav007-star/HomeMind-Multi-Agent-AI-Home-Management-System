"""Shared Contextual Memory implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from backend.simulation.models import GlobalHomeState
from backend.agents.schemas import CoordinatorDecision, AgentAlert
from backend.memory.models import ResidentProfile, ScheduleHabit


class SharedHomeMemory:
    """Maintains structured contextual memory: resident preferences, recurring schedules,

    event history, energy baselines, and past multi-agent decisions.
    """

    def __init__(self):
        # Resident preferences profile (Section 5)
        self.resident = ResidentProfile()

        # Recurring schedule habits
        self.habits: List[ScheduleHabit] = [
            ScheduleHabit(
                habit_id="habit_morning_wake",
                name="Morning Wakeup",
                window_start="06:45",
                window_end="07:20",
                target_state=GlobalHomeState.MORNING,
                description="Resident normally wakes up around 07:00 AM."
            ),
            ScheduleHabit(
                habit_id="habit_morning_departure",
                name="Weekday College/Work Departure",
                window_start="08:15",
                window_end="08:45",
                target_state=GlobalHomeState.AWAY,
                description="Resident normally departs for college/work at approximately 08:30 AM."
            ),
            ScheduleHabit(
                habit_id="habit_evening_return",
                name="Evening Arrival",
                window_start="17:15",
                window_end="18:00",
                target_state=GlobalHomeState.HOME,
                description="Resident typically returns home around 17:30 PM."
            ),
            ScheduleHabit(
                habit_id="habit_night_retire",
                name="Night Sleep",
                window_start="22:30",
                window_end="23:30",
                target_state=GlobalHomeState.SLEEP,
                description="Resident usually retires for sleep around 23:00 PM."
            ),
        ]

        # Historical archives
        self.decision_history: List[CoordinatorDecision] = []
        self.alert_history: List[AgentAlert] = []

        # Operational Baselines (Section 5)
        self.baselines: Dict[str, Any] = {
            "unoccupied_power_baseline_watts": 220.0,
            "expected_water_daily_liters": 220.0,
            "normal_leak_tolerance_lpm": 0.05,
            "preferred_comfort_temp_range": (self.resident.preferred_temp_min, self.resident.preferred_temp_max)
        }

    def _is_time_in_window(self, sim_time: datetime, start_str: str, end_str: str) -> bool:
        time_minutes = sim_time.hour * 60 + sim_time.minute
        s_h, s_m = map(int, start_str.split(":"))
        e_h, e_m = map(int, end_str.split(":"))
        start_minutes = s_h * 60 + s_m
        end_minutes = e_h * 60 + e_m
        return start_minutes <= time_minutes <= end_minutes

    def check_schedule_context(self, sim_time: datetime) -> Optional[ScheduleHabit]:
        """Checks if current simulation time corresponds to a known scheduled habit."""
        for habit in self.habits:
            if self._is_time_in_window(sim_time, habit.window_start, habit.window_end):
                return habit
        return None

    def get_departure_context(self, sim_time: datetime) -> Tuple[bool, str]:
        """Section 5 Example: Correlates home becoming unoccupied with known departure habits."""
        habit = self.check_schedule_context(sim_time)
        time_str = sim_time.strftime("%I:%M %p")
        if habit and habit.habit_id == "habit_morning_departure":
            return True, (
                f"At {time_str}, the home becoming unoccupied matches the resident's "
                f"typical departure habit (~08:30 AM). Interpreted as a normal planned routine."
            )
        else:
            return False, (
                f"At {time_str}, the home becoming unoccupied does not match any scheduled habit. "
                "Classified as an unscheduled vacancy event."
            )

    def record_decision(self, decision: CoordinatorDecision) -> None:
        """Stores decision in contextual memory."""
        self.decision_history.append(decision)
        if len(self.decision_history) > 50:
            self.decision_history.pop(0)

    def record_alert(self, alert: AgentAlert) -> None:
        """Stores alert in historical memory."""
        self.alert_history.append(alert)
        if len(self.alert_history) > 50:
            self.alert_history.pop(0)

    def get_summary(self) -> Dict[str, Any]:
        """Returns structured memory profile summary for dashboards and agents."""
        return {
            "resident_name": self.resident.name,
            "preferences": {
                "temp_min": self.resident.preferred_temp_min,
                "temp_max": self.resident.preferred_temp_max,
                "sleep_temp": self.resident.preferred_sleep_temp
            },
            "tracked_habits_count": len(self.habits),
            "decisions_archived_count": len(self.decision_history),
            "alerts_archived_count": len(self.alert_history),
            "baselines": self.baselines
        }

