"""Unit and integration tests for HomeMind FastAPI Backend & Dashboard API (Phase 8)."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_root_serves_html(client):
    """Test root endpoint serves the dashboard index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "HomeMind" in response.text
    assert "Five Specialized AI Agents" in response.text


def test_api_overview_endpoint(client):
    """Test /api/overview returns home telemetry, rooms, devices, and state."""
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()

    assert "sim_time" in data
    assert "home_state" in data
    assert "environment" in data
    assert "energy" in data
    assert "water" in data
    assert "security" in data
    assert "rooms" in data
    assert "devices" in data

    # Verify 5 standard rooms present
    assert len(data["rooms"]) == 5
    assert "living_room" in data["rooms"]
    assert "bedroom" in data["rooms"]
    assert "kitchen" in data["rooms"]
    assert "bathroom" in data["rooms"]
    assert "entrance" in data["rooms"]


def test_api_agents_endpoint(client):
    """Test /api/agents returns all 5 specialized agents."""
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()

    assert "agents" in data
    agents = data["agents"]
    assert "HOME_MANAGER" in agents
    assert "ENERGY" in agents
    assert "COMFORT" in agents
    assert "SECURITY" in agents
    assert "RESOURCE" in agents

    for ag_key, ag in agents.items():
        assert "status" in ag
        assert "current_task" in ag
        assert "latest_decision" in ag


def test_api_timeline_endpoint(client):
    """Test /api/timeline returns chronological collaboration event stream."""
    response = client.get("/api/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "timeline" in data
    assert len(data["timeline"]) > 0
    assert "event" in data["timeline"][0]
    assert "source" in data["timeline"][0]


def test_api_communication_matrix_endpoint(client):
    """Test /api/communication returns directed matrix nodes, edges and history."""
    response = client.get("/api/communication")
    assert response.status_code == 200
    data = response.json()
    assert "matrix" in data
    assert "nodes" in data["matrix"]
    assert "edges" in data["matrix"]
    assert len(data["matrix"]["nodes"]) == 5
    assert "recent_messages" in data


def test_api_chat_delegation(client):
    """Test /api/chat triggers Home Manager natural-language intent parsing and delegation."""
    response = client.post("/api/chat", json={"message": "Turn the house into sleep mode."})
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "SLEEP_MODE"
    assert "response" in data
    assert data["new_home_state"] == "SLEEP"
    assert len(data["actions_executed"]) > 0


def test_api_scenarios_execution(client):
    """Test triggering demonstration scenarios via API."""
    # Scenario 1: Morning
    res1 = client.post("/api/scenario/1")
    assert res1.status_code == 200
    report1 = res1.json()
    assert report1["scenario_id"] == "SCENARIO_1_MORNING"
    assert len(report1["steps"]) >= 6

    # Scenario 3: Water Leak Anomaly
    res3 = client.post("/api/scenario/3")
    assert res3.status_code == 200
    report3 = res3.json()
    assert report3["scenario_id"] == "SCENARIO_3_WATER_LEAK"
    assert len(report3["alerts"]) > 0


def test_api_simulation_tick(client):
    """Test advancing simulation clock via /api/simulation/tick."""
    res = client.post("/api/simulation/tick", json={"delta_seconds": 300})
    assert res.status_code == 200
    data = res.json()
    assert "sim_time" in data


def test_api_device_control(client):
    """Test controlling device power state."""
    # Turn ON living room light
    res_on = client.post("/api/simulation/device", json={"device_id": "light_living", "action": "TURN_ON"})
    assert res_on.status_code == 200
    assert res_on.json()["status"] == "success"

    # Turn OFF living room light
    res_off = client.post("/api/simulation/device", json={"device_id": "light_living", "action": "TURN_OFF"})
    assert res_off.status_code == 200
    assert res_off.json()["status"] == "success"


def test_api_anomaly_injection(client):
    """Test injecting water leak anomaly via API."""
    res = client.post("/api/simulation/anomaly", json={
        "anomaly_type": "WATER_LEAK",
        "active": True,
        "parameters": {"leak_rate_lpm": 3.8}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["overview"]["water"]["leak_detected"] is True

