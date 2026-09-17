# HomeMind — Multi-Agent AI Home Management System

HomeMind is an AI-agent-based home management system for an urban house/apartment. Instead of a single monolithic chatbot, five specialized AI agents collaborate within a shared home context to reason, make contextual decisions, and actuate home systems.

---

## Project Status: 100% Complete (All 12 Phases Implemented & Verified)

Following the 12-phase development roadmap (Section 20 of the Master Specification):
- **Phase 1: Core Home Simulation Engine** (Completed & Verified)
- **Phase 2: Five Agent Architecture** (Completed & Verified)
- **Phase 3: Home Manager Delegation Protocol** (Completed & Verified)
- **Phase 4: Agent-to-Agent Communication Bus** (Completed & Verified)
- **Phase 5: Shared Home State Machine** (Completed & Verified)
- **Phase 6: Contextual Memory & Habit Correlator** (Completed & Verified)
- **Phase 7: The Three Major Demonstration Scenarios** (Completed & Verified)
- **Phase 8: Modern Dashboard & API Integration** (Completed & Verified)
- **Phase 9: Natural-Language Interaction & LLM Integration** (Completed & Verified)
- **Phase 10: Explainable Decisions & Comprehensive Logging** (Completed & Verified)
- **Phase 11: Independent Agent Unit Testing Suite** (Completed & Verified)
- **Phase 12: Complete Multi-Agent Workflow End-to-End Verification** (Completed & Verified)

---

## Master Verification & Testing Suite

### 1. Section 21 Master Project Success Criteria Full Verification
Validate all 13 Master Project Success Criteria in a single automated pass:
```powershell
.\venv\Scripts\python.exe verify_full_system.py
```
Outputs `[PASS]` for every single criterion and verifies full cross-agent synchronization.

### 2. Full Pytest Test Suite (73 Automated Tests Passing)
```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```
All 73 unit and integration tests execute across all 12 phases in under 1 second.

---

## Explainability & Safety Architecture (`backend/explainability/`)

Adheres strictly to Sections 13, 16, & 18:
- **Decision Explanations (Section 13)**: Concise decision explanation cards based on observable inputs and actions, answering "Why?":
  - **Water Leak Incident**: Explains AWAY state + abnormal flow + zero motion + divergence from unoccupied baseline.
  - **Energy Shedding**: Explains room vacancy + appliance wattage + active shedding policy + peak tariff multipliers.
  - **Climate Adjustment**: Explains current room temperature + resident comfort bounds (22°C - 25.5°C) + target equilibrium setpoints.
  - **Conflict Arbitration**: Explains competing proposals between domain agents and resolution priority policies.
- **Safety Tiers (Section 16)**:
  - `SAFE_AUTONOMOUS`: Routine non-destructive actions (e.g. climate setpoints, dimming lights).
  - `RECOMMENDATION_ONLY`: Advisory suggestions (e.g. shopping restock items, peak-hour load shifting).
  - `REQUIRES_CONFIRMATION`: Potentially disruptive actions (e.g. closing main emergency water shutoff valve).
- **Comprehensive Audit Logging (`backend/explainability/logger.py`)**:
  - `logs/decision_log.jsonl`: Structured JSON Lines capturing complete records for computational inspection.
  - `logs/activity_audit.csv`: Human-friendly CSV audit log formatted for review and tabular analysis.

---

## Quick Start

### 1. Launch Modern Web Dashboard
```powershell
.\venv\Scripts\python.exe run_dashboard.py
```
Open **`http://127.0.0.1:8000`** in your browser. Features live digital twin controls, agent status telemetry, natural language chat, visual communication matrix, scenario triggers, and audit logs.

### 2. Run CLI Demos
- **Full System Verification**: `.\venv\Scripts\python.exe verify_full_system.py`
- **Explainable Decisions**: `.\venv\Scripts\python.exe demo_explainability.py`
- **Natural-Language Interaction**: `.\venv\Scripts\python.exe demo_nlp.py`
- **Three Demonstration Scenarios**: `.\venv\Scripts\python.exe demo_scenarios.py`
- **Agent Delegation Loop**: `.\venv\Scripts\python.exe demo_delegation.py`
- **Horizontal Inter-Agent Communication**: `.\venv\Scripts\python.exe demo_communication.py`
- **Shared Memory & State Machine**: `.\venv\Scripts\python.exe demo_memory.py`
- **Simulation Digital Twin**: `.\venv\Scripts\python.exe demo_simulation.py`
