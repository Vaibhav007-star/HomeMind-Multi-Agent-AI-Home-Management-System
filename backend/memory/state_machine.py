"""Global Home State Machine implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime

from backend.simulation.models import GlobalHomeState
from backend.memory.models import StatePolicy, StateTransitionRecord


class HomeStateMachine:
    """Manages formal global home states, transition rules, and operational policies."""

    def __init__(self, initial_state: GlobalHomeState = GlobalHomeState.HOME):
        self.current_state = initial_state
        self.transition_history: List[StateTransitionRecord] = []

        # Allowed state transition matrix (Section 4)
        self.allowed_transitions: Dict[GlobalHomeState, Set[GlobalHomeState]] = {
            GlobalHomeState.HOME: {
                GlobalHomeState.AWAY,
                GlobalHomeState.SLEEP,
                GlobalHomeState.MORNING,
                GlobalHomeState.EMERGENCY,
                GlobalHomeState.MAINTENANCE
            },
            GlobalHomeState.AWAY: {
                GlobalHomeState.HOME,
                GlobalHomeState.EMERGENCY,
                GlobalHomeState.MAINTENANCE
            },
            GlobalHomeState.SLEEP: {
                GlobalHomeState.MORNING,
                GlobalHomeState.HOME,
                GlobalHomeState.EMERGENCY,
                GlobalHomeState.MAINTENANCE
            },
            GlobalHomeState.MORNING: {
                GlobalHomeState.HOME,
                GlobalHomeState.AWAY,
                GlobalHomeState.EMERGENCY,
                GlobalHomeState.MAINTENANCE
            },
            GlobalHomeState.EMERGENCY: {
                GlobalHomeState.HOME,
                GlobalHomeState.MAINTENANCE
            },
            GlobalHomeState.MAINTENANCE: {
                GlobalHomeState.HOME,
                GlobalHomeState.AWAY
            }
        }

        # Operational policies per home state (Section 4)
        self.policies: Dict[GlobalHomeState, StatePolicy] = {
            GlobalHomeState.HOME: StatePolicy(
                state=GlobalHomeState.HOME,
                max_discretionary_watts=3500.0,
                security_armed=False,
                strict_perimeter=False,
                allow_vacant_room_cooling=False,
                lock_doors_required=False,
                dim_lights_required=False,
                description="Normal daytime home operations prioritizing resident comfort and productivity."
            ),
            GlobalHomeState.AWAY: StatePolicy(
                state=GlobalHomeState.AWAY,
                max_discretionary_watts=0.0,
                security_armed=True,
                strict_perimeter=True,
                allow_vacant_room_cooling=False,
                lock_doors_required=True,
                dim_lights_required=True,
                description="Residence is vacant. Power conservation minimized, perimeter defense armed, resource alerts strict."
            ),
            GlobalHomeState.SLEEP: StatePolicy(
                state=GlobalHomeState.SLEEP,
                max_discretionary_watts=200.0,
                security_armed=True,
                strict_perimeter=True,
                allow_vacant_room_cooling=False,
                lock_doors_required=True,
                dim_lights_required=True,
                description="Night sleep mode. Discretionary lighting off, bedroom climate quiet and restful, perimeter secured."
            ),
            GlobalHomeState.MORNING: StatePolicy(
                state=GlobalHomeState.MORNING,
                max_discretionary_watts=2500.0,
                security_armed=False,
                strict_perimeter=False,
                allow_vacant_room_cooling=False,
                lock_doors_required=False,
                dim_lights_required=False,
                description="Morning wake routine. Environment gently adjusted, resources and energy audited."
            ),
            GlobalHomeState.EMERGENCY: StatePolicy(
                state=GlobalHomeState.EMERGENCY,
                max_discretionary_watts=0.0,
                security_armed=True,
                strict_perimeter=True,
                allow_vacant_room_cooling=False,
                lock_doors_required=True,
                dim_lights_required=False,
                description="Active safety incident. Discretionary devices isolated, alerts broadcast."
            ),
            GlobalHomeState.MAINTENANCE: StatePolicy(
                state=GlobalHomeState.MAINTENANCE,
                max_discretionary_watts=1500.0,
                security_armed=False,
                strict_perimeter=False,
                allow_vacant_room_cooling=False,
                lock_doors_required=False,
                dim_lights_required=False,
                description="Maintenance mode for appliance repairs, servicing, or plumbing leak resolution."
            )
        }

    def can_transition(self, target_state: GlobalHomeState) -> bool:
        """Evaluates whether the proposed state transition is permissible."""
        if target_state == self.current_state:
            return True
        allowed = self.allowed_transitions.get(self.current_state, set())
        return target_state in allowed

    def transition_to(
        self,
        target_state: GlobalHomeState,
        reason: str,
        initiator: str = "HomeManager"
    ) -> Tuple[bool, Optional[StateTransitionRecord]]:
        """Executes state transition if valid and records audit entry."""
        if not self.can_transition(target_state):
            return False, None

        record = StateTransitionRecord(
            from_state=self.current_state,
            to_state=target_state,
            trigger_reason=reason,
            initiator=initiator
        )
        self.current_state = target_state
        self.transition_history.append(record)
        return True, record

    def get_active_policy(self) -> StatePolicy:
        """Returns the operational rule set for the active global home state."""
        return self.policies[self.current_state]

    def get_transition_history(self) -> List[StateTransitionRecord]:
        """Returns chronological state transition logs."""
        return list(self.transition_history)

