"""Unit and integration tests for Natural-Language Interaction & NLP Engine (Phase 9)."""

import pytest
from backend.agents.nlp_engine import NLPEngine, LLMProvider
from backend.agents.schemas import AgentType, ActionPriority, AgentAlert
from backend.agents.orchestration import AgentTaskResult
from backend.simulation.models import GlobalHomeState
from backend.simulation.simulator import HomeSimulator
from backend.agents.home_manager import HomeManagerAgent


@pytest.fixture
def nlp():
    return NLPEngine(provider=LLMProvider.DETERMINISTIC)


def test_nlp_intent_leaving_home(nlp):
    """Test diverse departure phrasings map accurately to LEAVING_HOME."""
    phrases = [
        "I'm leaving for college.",
        "Heading out to class now, bye!",
        "Going to work, see you later.",
        "Leaving home."
    ]
    for p in phrases:
        plan = nlp.understand_intent(p, current_state=GlobalHomeState.HOME)
        assert plan.intent == "LEAVING_HOME"
        assert plan.target_home_state == GlobalHomeState.AWAY
        assert len(plan.tasks) == 4
        recipients = [t.recipient for t in plan.tasks]
        assert AgentType.ENERGY in recipients
        assert AgentType.COMFORT in recipients
        assert AgentType.SECURITY in recipients
        assert AgentType.RESOURCE in recipients


def test_nlp_intent_sleep_mode(nlp):
    """Test sleep phrasings map to SLEEP_MODE."""
    phrases = [
        "Turn the house into sleep mode.",
        "Time for bed.",
        "Goodnight, going to sleep.",
        "Retiring for the night."
    ]
    for p in phrases:
        plan = nlp.understand_intent(p, current_state=GlobalHomeState.HOME)
        assert plan.intent == "SLEEP_MODE"
        assert plan.target_home_state == GlobalHomeState.SLEEP
        assert len(plan.tasks) >= 3


def test_nlp_intent_return_home(nlp):
    """Test arrival phrasings map to RETURN_HOME."""
    phrases = [
        "I'm back home.",
        "Just returned from college.",
        "Arrived home."
    ]
    for p in phrases:
        plan = nlp.understand_intent(p, current_state=GlobalHomeState.AWAY)
        assert plan.intent == "RETURN_HOME"
        assert plan.target_home_state == GlobalHomeState.HOME


def test_nlp_intent_energy_query(nlp):
    """Test Section 12 Question 3: 'Why is the energy consumption high?'."""
    phrases = [
        "Why is the energy consumption high?",
        "What is our electricity wattage right now?",
        "Check power usage."
    ]
    for p in phrases:
        plan = nlp.understand_intent(p, current_state=GlobalHomeState.HOME)
        assert plan.intent == "ENERGY_AUDIT"
        assert plan.target_home_state is None
        assert plan.tasks[0].recipient == AgentType.ENERGY


def test_nlp_intent_security_query(nlp):
    """Test Section 12 Question 4: 'Is everything okay at home?'."""
    phrases = [
        "Is everything okay at home?",
        "Are the doors locked and house safe?",
        "What is our security status?"
    ]
    for p in phrases:
        plan = nlp.understand_intent(p, current_state=GlobalHomeState.HOME)
        assert plan.intent == "SECURITY_STATUS"
        recipients = [t.recipient for t in plan.tasks]
        assert AgentType.SECURITY in recipients


def test_nlp_intent_grocery_query(nlp):
    """Test Section 12 Question 5: 'Do we need to buy anything?'."""
    phrases = [
        "Do we need to buy anything?",
        "What groceries are running low?",
        "Show shopping supplies."
    ]
    for p in phrases:
        plan = nlp.understand_intent(p, current_state=GlobalHomeState.HOME)
        assert plan.intent == "GROCERY_CHECK"
        assert plan.tasks[0].recipient == AgentType.RESOURCE


def test_nlp_natural_response_generation(nlp):
    """Verify natural language response contains explainable agent summaries."""
    agent_results = {
        "ENERGY": AgentTaskResult(
            task_id="t1",
            agent_type=AgentType.ENERGY,
            success=True,
            actions_executed=["Turned off Living TV"],
            report="Deactivated 2 discretionary loads, saving 110 W.",
            data={"total_watts": 340, "running_loads": "Fridge"}
        ),
        "SECURITY": AgentTaskResult(
            task_id="t2",
            agent_type=AgentType.SECURITY,
            success=True,
            actions_executed=["Locked front door"],
            report="Perimeter secured: Front door locked, away sensors armed.",
            data={"lock_state": "LOCKED"}
        )
    }

    response = nlp.generate_natural_response(
        intent="LEAVING_HOME",
        user_prompt="I'm leaving for college.",
        rationale="Resident departing.",
        target_state=GlobalHomeState.AWAY,
        agent_results=agent_results
    )

    assert "Home Manager Response" in response
    assert "Energy Agent" in response
    assert "Security Agent" in response
    assert "110 W" in response
    assert "LOCKED" in response or "locked" in response


def test_nlp_anomaly_explanation(nlp):
    """Verify Section 13 decision explanation formatting."""
    alert = AgentAlert(
        agent_type=AgentType.HOME_MANAGER,
        title="Cross-Agent Correlated Incident: Possible Water Leak",
        severity="CRITICAL",
        description="Resource Agent reports abnormal water flow while Security Agent confirms zero resident activity.",
        evidence=[
            "Water outflow: 4.2 L/min",
            "Motion detected: False in all 5 rooms",
            "Home state: AWAY"
        ],
        recommended_action="Emergency shutoff valve closure."
    )

    explanation = nlp.explain_anomaly(alert, alert.evidence)
    assert "Possible Water Leak" in explanation
    assert "CRITICAL" in explanation
    assert "4.2 L/min" in explanation
    assert "Emergency shutoff" in explanation


def test_home_manager_workflow_nlp_integration():
    """Verify HomeManager executes end-to-end workflow using NLP engine."""
    manager = HomeManagerAgent()
    sim = HomeSimulator()

    # Query: Why is the energy consumption high?
    wf1 = manager.execute_workflow("Why is the energy consumption high?", sim)
    assert wf1.intent == "ENERGY_AUDIT"
    assert "ENERGY" in wf1.agent_results
    assert len(wf1.final_response) > 30

    # Query: Do we need to buy anything?
    wf2 = manager.execute_workflow("Do we need to buy anything?", sim)
    assert wf2.intent == "GROCERY_CHECK"
    assert "RESOURCE" in wf2.agent_results
    assert "Inventory" in wf2.final_response or "Supplies" in wf2.final_response

