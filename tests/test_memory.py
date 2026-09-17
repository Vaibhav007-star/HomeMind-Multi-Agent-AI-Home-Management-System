"""Unit and integration tests for Shared Home State Machine & Contextual Memory (Phase 5 & 6)."""

import pytest
from datetime import datetime
from backend.simulation.models import GlobalHomeState
from backend.simulation.simulator import HomeSimulator
from backend.memory import (
    HomeStateMachine,
    SharedHomeMemory,
    ResidentProfile,
    ScheduleHabit
)
from backend.agents import HomeManagerAgent, CoordinatorDecision


def test_state_machine_valid_transitions():
    """Verify state machine transition lifecycle: HOME -> AWAY -> HOME -> SLEEP -> MORNING -> HOME."""
    sm = HomeStateMachine(initial_state=GlobalHomeState.HOME)
    assert sm.current_state == GlobalHomeState.HOME

    # HOME -> AWAY
    ok, rec = sm.transition_to(GlobalHomeState.AWAY, reason="Resident left for college")
    assert ok is True
    assert rec is not None
    assert sm.current_state == GlobalHomeState.AWAY

    # AWAY -> HOME
    ok, _ = sm.transition_to(GlobalHomeState.HOME, reason="Resident returned")
    assert ok is True
    assert sm.current_state == GlobalHomeState.HOME

    # HOME -> SLEEP
    ok, _ = sm.transition_to(GlobalHomeState.SLEEP, reason="Bedtime")
    assert ok is True
    assert sm.current_state == GlobalHomeState.SLEEP

    # SLEEP -> MORNING
    ok, _ = sm.transition_to(GlobalHomeState.MORNING, reason="Alarm 7:00 AM")
    assert ok is True
    assert sm.current_state == GlobalHomeState.MORNING

    # MORNING -> HOME
    ok, _ = sm.transition_to(GlobalHomeState.HOME, reason="Breakfast complete")
    assert ok is True
    assert sm.current_state == GlobalHomeState.HOME

    assert len(sm.get_transition_history()) == 5


def test_state_machine_invalid_transitions():
    """Verify disallowed state transitions are rejected with integrity preserved."""
    sm = HomeStateMachine(initial_state=GlobalHomeState.SLEEP)

    # SLEEP cannot jump directly to AWAY
    assert sm.can_transition(GlobalHomeState.AWAY) is False
    ok, rec = sm.transition_to(GlobalHomeState.AWAY, reason="Invalid jump")
    assert ok is False
    assert rec is None
    assert sm.current_state == GlobalHomeState.SLEEP


def test_state_policies():
    """Verify domain policy constraints associated with each home state."""
    sm = HomeStateMachine()

    # AWAY policy
    sm.transition_to(GlobalHomeState.AWAY, reason="Test away")
    away_policy = sm.get_active_policy()
    assert away_policy.security_armed is True
    assert away_policy.max_discretionary_watts == 0.0
    assert away_policy.strict_perimeter is True

    # SLEEP policy
    sm.transition_to(GlobalHomeState.HOME, reason="Return")
    sm.transition_to(GlobalHomeState.SLEEP, reason="Bedtime")
    sleep_policy = sm.get_active_policy()
    assert sleep_policy.lock_doors_required is True
    assert sleep_policy.dim_lights_required is True


def test_contextual_habit_schedule_recognition():
    """Verify Section 5 Example: Correlating events at 8:30 AM with resident departure habits."""
    memory = SharedHomeMemory()

    # 8:30 AM simulation time (Matches departure habit window 08:15 - 08:45)
    morning_departure_time = datetime(2026, 9, 17, 8, 30, 0)
    is_habit, explanation = memory.get_departure_context(morning_departure_time)
    assert is_habit is True
    assert "typical departure habit" in explanation

    # 2:15 AM simulation time (Anomalous / unscheduled vacancy)
    middle_of_night_time = datetime(2026, 9, 17, 2, 15, 0)
    is_habit_night, explanation_night = memory.get_departure_context(middle_of_night_time)
    assert is_habit_night is False
    assert "unscheduled vacancy event" in explanation_night


def test_context_memory_archiving():
    """Verify archiving and summary generation for decisions and alerts."""
    memory = SharedHomeMemory()

    dec = CoordinatorDecision(
        home_state="HOME",
        summary="Test multi-agent decision",
        explanation="Testing decision logging"
    )
    memory.record_decision(dec)

    summary = memory.get_summary()
    assert summary["resident_name"] == "Alex Morgan"
    assert summary["decisions_archived_count"] == 1
    assert summary["tracked_habits_count"] >= 4


def test_home_manager_workflow_with_state_machine_and_memory():
    """Verify end-to-end integration: workflow triggers state machine transition and memory archiving."""
    sim = HomeSimulator(start_hour=8, start_minute=30)
    manager = HomeManagerAgent()

    result = manager.execute_workflow("I'm leaving for college.", sim)

    # State Machine should have transitioned to AWAY
    assert manager.state_machine.current_state == GlobalHomeState.AWAY
    assert sim.global_home_state == GlobalHomeState.AWAY

    # Contextual memory habit recognized in timeline
    assert any("Contextual Memory" in item["source"] for item in result.timeline)
    assert any("typical departure habit" in item["event"] for item in result.timeline)

    # Contextual memory archived decision
    mem_summary = manager.get_memory_summary()
    assert mem_summary["current_state"] == "AWAY"
    assert mem_summary["transition_count"] >= 1
    assert mem_summary["memory_summary"]["decisions_archived_count"] >= 1

