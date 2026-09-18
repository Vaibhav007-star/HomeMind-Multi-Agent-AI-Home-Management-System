"""FastAPI backend application for HomeMind Multi-Agent Home Management System."""

from __future__ import annotations
import asyncio
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from backend.simulation.simulator import HomeSimulator
from backend.simulation.models import (
    GlobalHomeState,
    DevicePowerState,
    LockState,
    DoorState,
    HomeStateSnapshot
)
from backend.agents.home_manager import HomeManagerAgent
from backend.agents.schemas import AgentType, AgentStatusEnum
from backend.scenarios.runner import ScenarioRunner
from backend.scenarios.models import ScenarioReport
from backend.explainability import ExplanationEngine, AuditLogger, DecisionExplanation, SafetyTier


# Request / Response Models
class ChatRequest(BaseModel):
    message: str


class TickRequest(BaseModel):
    delta_seconds: int = 60


class DeviceControlRequest(BaseModel):
    device_id: str
    action: str  # "TURN_ON", "TURN_OFF", "SET_TEMP", "LOCK", "UNLOCK"
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AnomalyInjectionRequest(BaseModel):
    anomaly_type: str  # "WATER_LEAK", "DOOR_OPEN", "HIGH_CONSUMPTION"
    active: bool = True
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ConnectionManager:
    """Manages active real-time WebSocket clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


class HomeMindService:
    """Core coordinator wrapping the Digital Twin, 5 Agents, and Context."""

    def __init__(self):
        self.sim = HomeSimulator(start_hour=7, start_minute=0)
        self.manager = HomeManagerAgent()
        self.runner = ScenarioRunner(simulator=self.sim, manager=self.manager)
        self.logger = AuditLogger()
        self.timeline: List[Dict[str, Any]] = []
        self._init_timeline()

    def _init_timeline(self):
        time_str = self.sim.sim_time.strftime("%H:%M")
        self.timeline.append({
            "id": 1,
            "time": time_str,
            "source": "Home Manager",
            "event": "HomeMind Multi-Agent System initialized. 5 agents active.",
            "type": "SYSTEM",
            "evidence": ["Digital twin calibrated", "Agent communication bus mounted"]
        })
        self.timeline.append({
            "id": 2,
            "time": time_str,
            "source": "State Machine",
            "event": "Initial Global Home State established: HOME.",
            "type": "STATE_CHANGE",
            "evidence": ["Policy: HOME mode daytime baselines active"]
        })
        init_exp = ExplanationEngine.explain_state_transition(
            from_state=GlobalHomeState.SLEEP,
            to_state=GlobalHomeState.HOME,
            initiator="SystemStartup",
            rationale="Initial daytime baseline established."
        )
        self.logger.log_decision(init_exp)

    def record_timeline_event(self, source: str, event: str, event_type: str = "ACTION", evidence: Optional[List[str]] = None):
        time_str = self.sim.sim_time.strftime("%H:%M")
        self.timeline.insert(0, {
            "id": len(self.timeline) + 1,
            "time": time_str,
            "source": source,
            "event": event,
            "type": event_type,
            "evidence": evidence or []
        })
        # Keep latest 100 events
        if len(self.timeline) > 100:
            self.timeline.pop()

    def get_overview(self) -> Dict[str, Any]:
        snapshot = self.sim.get_snapshot()
        avg_temp = sum(r.temperature_celsius for r in snapshot.rooms.values()) / max(1, len(snapshot.rooms))
        avg_humidity = sum(r.humidity_percent for r in snapshot.rooms.values()) / max(1, len(snapshot.rooms))
        occupied_rooms = [r.room_name for r in snapshot.rooms.values() if r.occupied]

        return {
            "sim_time": self.sim.sim_time.strftime("%I:%M %p"),
            "sim_time_24": self.sim.sim_time.strftime("%H:%M"),
            "home_state": self.sim.global_home_state.value,
            "weather": {
                "outdoor_temp": round(snapshot.outdoor_temperature_celsius, 1),
                "outdoor_humidity": round(snapshot.outdoor_humidity_percent, 1),
                "solar_radiation": round(self.sim.env.solar_heat_gain * 600.0, 1),
                "is_daylight": (6 <= self.sim.sim_time.hour <= 18)
            },
            "environment": {
                "avg_temperature": round(avg_temp, 1),
                "avg_humidity": round(avg_humidity, 1),
                "occupied_count": len(occupied_rooms),
                "occupied_rooms": occupied_rooms,
            },
            "energy": {
                "instant_power_watts": round(snapshot.energy_system.instant_power_watts, 1),
                "daily_energy_kwh": round(snapshot.energy_system.daily_energy_kwh, 3),
                "carbon_intensity_g_kwh": 480.0,
                "is_peak_pricing": (18 <= self.sim.sim_time.hour <= 22)
            },
            "water": {
                "tank_liters": round(snapshot.water_system.current_water_liters, 1),
                "tank_capacity": round(self.sim.env.water_tank_capacity_liters, 1),
                "tank_percent": round(snapshot.water_system.water_level_percent, 1),
                "flow_rate_lpm": round(snapshot.water_system.flow_rate_lpm, 2),
                "pump_active": snapshot.water_system.pump_active,
                "leak_detected": snapshot.water_system.leak_rate_lpm > 0.0
            },
            "security": {
                "door_state": snapshot.security_system.entrance_door_state.value,
                "lock_state": snapshot.security_system.entrance_lock_state.value,
                "away_mode_armed": snapshot.security_system.away_mode_armed,
                "security_alert": snapshot.security_system.security_alerts_count > 0
            },
            "rooms": {
                r_id: {
                    "room_id": r.room_id,
                    "name": r.room_name,
                    "temperature": round(r.temperature_celsius, 1),
                    "humidity": round(r.humidity_percent, 1),
                    "occupied": r.occupied,
                    "motion": r.motion_detected
                }
                for r_id, r in snapshot.rooms.items()
            },
            "devices": {
                d_id: {
                    "device_id": d.device_id,
                    "name": d.name,
                    "room_id": d.room_id,
                    "device_type": d.device_type.value,
                    "power_state": d.power_state.value,
                    "power_draw_watts": round(d.get_current_power_draw(), 1),
                    "attributes": d.attributes
                }
                for d_id, d in self.sim.devices.items()
            }
        }

    def get_agents(self) -> Dict[str, Any]:
        snapshot = self.sim.get_snapshot()
        sub_evals = self.manager.delegate_all(snapshot)
        manager_eval = self.manager.evaluate(snapshot)

        def serialize_alert(a):
            return {
                "alert_id": a.alert_id,
                "agent_type": a.agent_type.value if hasattr(a.agent_type, "value") else str(a.agent_type),
                "title": a.title,
                "severity": a.severity,
                "description": a.description,
                "evidence": a.evidence,
                "recommended_action": a.recommended_action
            }

        def serialize_rec(r):
            return {
                "action_id": r.action_id,
                "agent_type": r.agent_type.value if hasattr(r.agent_type, "value") else str(r.agent_type),
                "target_type": r.target_type,
                "target_id": r.target_id,
                "action": r.action,
                "priority": r.priority.value if hasattr(r.priority, "value") else str(r.priority),
                "reason": r.reason,
                "evidence": r.explainable_evidence
            }

        agents_data = {}
        for agent_type, sub_agent in self.manager.sub_agents.items():
            agent_eval = sub_evals.get(agent_type)
            agents_data[agent_type.value] = {
                "agent_type": agent_type.value,
                "name": sub_agent.name,
                "role": sub_agent.role,
                "status": sub_agent.status.value,
                "current_task": sub_agent.current_task,
                "latest_decision": sub_agent.latest_decision,
                "important_event": agent_eval.summary if agent_eval else "Active monitoring and telemetry tracking.",
                "metrics": agent_eval.metrics if agent_eval else {},
                "alerts": [serialize_alert(a) for a in agent_eval.alerts] if agent_eval else [],
                "recommendations": [serialize_rec(r) for r in agent_eval.recommendations] if agent_eval else []
            }

        # Central Home Manager
        agents_data["HOME_MANAGER"] = {
            "agent_type": "HOME_MANAGER",
            "name": self.manager.name,
            "role": self.manager.role,
            "status": self.manager.status.value,
            "current_task": self.manager.current_task,
            "latest_decision": self.manager.latest_decision,
            "important_event": f"Active state: {self.sim.global_home_state.value}. Coordinating all 4 specialized agents.",
            "metrics": manager_eval.metrics,
            "alerts": [serialize_alert(a) for a in manager_eval.alerts],
            "recommendations": [serialize_rec(r) for r in manager_eval.recommendations]
        }

        return {
            "agents": agents_data,
            "coordinator_summary": manager_eval.summary,
            "total_alerts": len(manager_eval.alerts)
        }

    def get_communication_matrix(self) -> Dict[str, Any]:
        matrix = self.manager.bus.get_communication_matrix()
        all_msgs = self.manager.bus.get_all_messages()
        history = [
            {
                "msg_id": getattr(m, "message_id", getattr(m, "msg_id", "")),
                "timestamp": m.timestamp.strftime("%H:%M:%S"),
                "sender": m.sender.value if hasattr(m.sender, "value") else str(m.sender),
                "receiver": m.receiver.value if hasattr(m.receiver, "value") else str(m.receiver),
                "msg_type": m.msg_type.value if hasattr(m.msg_type, "value") else str(m.msg_type),
                "topic": m.topic,
                "content": m.content,
                "payload": m.payload
            }
            for m in reversed(all_msgs[-25:])
        ]
        return {
            "matrix": matrix,
            "recent_messages": history
        }

    def handle_chat(self, prompt: str) -> Dict[str, Any]:
        workflow = self.manager.execute_workflow(prompt, self.sim)

        # Append workflow timeline events
        for item in workflow.timeline:
            self.record_timeline_event(
                source=item["source"],
                event=item["event"],
                event_type="ACTION" if "Executed" in item["event"] else "ANALYSIS"
            )

        return {
            "intent": workflow.intent,
            "rationale": workflow.delegation_plan.rationale,
            "response": workflow.final_response,
            "actions_executed": workflow.actions_applied,
            "timeline": workflow.timeline,
            "new_home_state": self.sim.global_home_state.value
        }

    def execute_scenario(self, scenario_id: str) -> ScenarioReport:
        sid = scenario_id.lower()
        if sid in ["1", "morning", "scenario_1"]:
            report = self.runner.run_scenario_1_morning()
        elif sid in ["2", "leaving", "scenario_2"]:
            report = self.runner.run_scenario_2_leaving()
        elif sid in ["3", "leak", "water_leak", "scenario_3"]:
            report = self.runner.run_scenario_3_water_leak()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown scenario ID: {scenario_id}")

        for step in report.steps:
            self.record_timeline_event(
                source=step.actor,
                event=step.description,
                event_type=step.action_type,
                evidence=step.evidence
            )

        # Log Section 13 explainable decision records
        if sid in ["3", "leak", "water_leak", "scenario_3"] and report.alerts:
            exp = ExplanationEngine.explain_water_leak_alert(
                alert=report.alerts[0],
                snapshot=self.sim.get_snapshot(),
                leak_rate_lpm=4.2
            )
            self.logger.log_decision(exp)
        elif sid in ["2", "leaving", "scenario_2"]:
            exp = ExplanationEngine.explain_state_transition(
                from_state=GlobalHomeState.HOME,
                to_state=GlobalHomeState.AWAY,
                initiator="Scenario2_Leaving",
                rationale="Resident departed for college; automated loads shed and perimeter secured."
            )
            self.logger.log_decision(exp)
        elif sid in ["1", "morning", "scenario_1"]:
            exp = ExplanationEngine.explain_state_transition(
                from_state=GlobalHomeState.SLEEP,
                to_state=GlobalHomeState.HOME,
                initiator="Scenario1_Morning",
                rationale="Morning routine complete; climate and perimeter adjusted."
            )
            self.logger.log_decision(exp)

        return report

    def tick(self, delta_seconds: int = 60) -> Dict[str, Any]:
        self.sim.tick(delta_seconds=delta_seconds)
        # Periodic agent evaluation to update status
        snapshot = self.sim.get_snapshot()
        self.manager.delegate_all(snapshot)
        return self.get_overview()

    def control_device(self, req: DeviceControlRequest) -> Dict[str, Any]:
        dev_id = req.device_id
        action = req.action.upper()

        if dev_id == "lock_entrance":
            if action in ["LOCK", "TURN_OFF"]:
                self.sim.set_lock_state(True)
                self.record_timeline_event("User", "Smart lock manually LOCKED", "ACTION")
            else:
                self.sim.set_lock_state(False)
                self.record_timeline_event("User", "Smart lock manually UNLOCKED", "ACTION")
            return {"status": "success", "device_id": dev_id, "action": action}

        if action == "TURN_ON":
            self.sim.set_device_power(dev_id, DevicePowerState.ON)
            self.record_timeline_event("User", f"Turned ON device {dev_id}", "ACTION")
        elif action == "TURN_OFF":
            self.sim.set_device_power(dev_id, DevicePowerState.OFF)
            self.record_timeline_event("User", f"Turned OFF device {dev_id}", "ACTION")
        elif action == "SET_TEMP":
            temp = float(req.parameters.get("temperature", 24.0))
            self.sim.set_ac_target(dev_id, temp)
            self.record_timeline_event("User", f"Set {dev_id} target temperature to {temp}°C", "ACTION")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

        return {"status": "success", "device_id": dev_id, "action": action}


# Initialize FastAPI App and Service
app = FastAPI(
    title="HomeMind — Multi-Agent AI Home Management System",
    description="Academic Multi-Agent Architecture for Smart Home Coordination",
    version="1.0.0"
)

service = HomeMindService()
ws_manager = ConnectionManager()

# Mount frontend static directory
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def root():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"message": "HomeMind API is running. Frontend index.html not yet deployed."})


@app.get("/3d")
@app.get("/twin3d")
async def twin3d_view():
    """Interactive 3D Motion Digital Twin Website View."""
    twin_file = frontend_dir / "twin3d.html"
    if twin_file.exists():
        return FileResponse(str(twin_file))
    return FileResponse(str(frontend_dir / "index.html"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Handle browser favicon request cleanly."""
    fav_file = frontend_dir / "favicon.ico"
    if fav_file.exists():
        return FileResponse(str(fav_file))
    svg_file = frontend_dir / "favicon.svg"
    if svg_file.exists():
        return FileResponse(str(svg_file), media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/api/overview")
async def get_overview():
    """Section 9: Complete Home Overview snapshot."""
    return service.get_overview()


@app.get("/api/agents")
async def get_agents():
    """Section 9: Real-time status, tasks, decisions and alerts of all 5 agents."""
    return service.get_agents()


@app.get("/api/timeline")
async def get_timeline():
    """Section 10: Chronological agent collaboration timeline."""
    return {"timeline": service.timeline}


@app.get("/api/communication")
async def get_communication():
    """Section 11: Agent-to-Agent Communication Matrix and recent bus dispatches."""
    return service.get_communication_matrix()


@app.post("/api/chat")
async def post_chat(req: ChatRequest):
    """Section 12: Natural-language interaction with Home Manager delegation."""
    result = service.handle_chat(req.message)
    await ws_manager.broadcast({"type": "STATE_UPDATE", "data": service.get_overview()})
    return result


@app.post("/api/scenario/{scenario_id}")
async def run_scenario(scenario_id: str):
    """Section 8: Trigger one of the 3 primary demonstration scenarios."""
    report = service.execute_scenario(scenario_id)
    await ws_manager.broadcast({"type": "SCENARIO_EXECUTED", "scenario_id": scenario_id})
    return report


@app.post("/api/simulation/tick")
async def post_tick(req: TickRequest):
    """Advance digital twin physics clock by delta_seconds."""
    overview = service.tick(req.delta_seconds)
    await ws_manager.broadcast({"type": "STATE_UPDATE", "data": overview})
    return overview


@app.post("/api/simulation/device")
async def post_device_control(req: DeviceControlRequest):
    """Directly toggle or configure a home device."""
    result = service.control_device(req)
    await ws_manager.broadcast({"type": "STATE_UPDATE", "data": service.get_overview()})
    return result


@app.post("/api/simulation/anomaly")
async def post_anomaly(req: AnomalyInjectionRequest):
    """Inject or clear anomalies (e.g. water leak, door forced open)."""
    if req.anomaly_type == "WATER_LEAK":
        rate = float(req.parameters.get("leak_rate_lpm", 4.2))
        service.sim.set_water_leak(req.active, leak_rate_lpm=rate)
        service.record_timeline_event(
            "Plumbing Sensor",
            f"Water leak {'injected at ' + str(rate) + ' L/min' if req.active else 'cleared'}.",
            "ALERT" if req.active else "ACTION"
        )
    elif req.anomaly_type == "DOOR_OPEN":
        service.sim.set_door_state(req.active)
        service.record_timeline_event(
            "Door Sensor",
            f"Front door set to {'OPEN' if req.active else 'CLOSED'}.",
            "ALERT" if req.active else "ACTION"
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported anomaly type")

    overview = service.get_overview()
    await ws_manager.broadcast({"type": "STATE_UPDATE", "data": overview})
    return {"status": "success", "overview": overview}


@app.get("/api/explanations")
async def get_explanations(limit: int = 20, decision_type: Optional[str] = None):
    """Section 13: Structured explainable decision cards with causal evidence."""
    return {"explanations": service.logger.get_recent(limit=limit, decision_type=decision_type)}


@app.get("/api/logs")
async def get_logs(limit: int = 50):
    """Section 16 & 20: Audit logs for faculty review."""
    return {
        "log_files": {
            "jsonl": str(service.logger.jsonl_path),
            "csv": str(service.logger.csv_path)
        },
        "recent_entries": service.logger.get_recent(limit=limit)
    }


@app.post("/api/explanations/{explanation_id}/confirm")
async def confirm_action(explanation_id: str):
    """Section 16: User confirmation for sensitive action (e.g. valve shutoff)."""
    for exp in service.logger.memory_buffer:
        if exp.explanation_id == explanation_id:
            exp.user_confirmed = True
            service.record_timeline_event(
                "User",
                f"Confirmed action for '{exp.title}': {exp.recommended_action}",
                "ACTION"
            )
            return {"status": "confirmed", "explanation": exp}
    raise HTTPException(status_code=404, detail="Explanation not found")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time dashboard updates."""
    await ws_manager.connect(websocket)
    try:
        # Send initial snapshot upon connection
        await websocket.send_json({
            "type": "INIT",
            "overview": service.get_overview(),
            "agents": service.get_agents(),
            "timeline": service.timeline,
            "communication": service.get_communication_matrix()
        })
        while True:
            data = await websocket.receive_text()
            # Echo ping / keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
