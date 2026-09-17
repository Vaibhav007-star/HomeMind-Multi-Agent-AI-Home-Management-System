"""Persistent audit logging for HomeMind multi-agent decisions and explainability cards (Phase 10)."""

from __future__ import annotations
import os
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from backend.explainability.models import DecisionExplanation, SafetyTier
from backend.agents.schemas import AgentType


class AuditLogger:
    """Manages persistent disk and in-memory logging of all multi-agent explainable decisions."""

    def __init__(self, log_dir: Optional[Any] = None):
        self.log_dir = Path(log_dir) if log_dir else (Path(__file__).resolve().parent.parent.parent / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.log_dir / "decision_log.jsonl"
        self.csv_path = self.log_dir / "activity_audit.csv"

        self.memory_buffer: List[DecisionExplanation] = []
        self._init_csv_header()

    def _init_csv_header(self):
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "explanation_id",
                    "origin_agent",
                    "decision_type",
                    "title",
                    "safety_tier",
                    "summary",
                    "why_reasons"
                ])

    def log_decision(self, explanation: DecisionExplanation) -> None:
        """Appends decision explanation to memory buffer and disk files."""
        # 1. Memory buffer
        self.memory_buffer.insert(0, explanation)
        if len(self.memory_buffer) > 100:
            self.memory_buffer.pop()

        # 2. Append to JSONL
        try:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                rec = explanation.model_dump(mode="json")
                f.write(json.dumps(rec) + "\n")
        except Exception as e:
            print(f"[WARN] Failed to write to {self.jsonl_path}: {e}")

        # 3. Append to CSV
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    explanation.timestamp.isoformat(),
                    explanation.explanation_id,
                    explanation.origin_agent.value,
                    explanation.decision_type,
                    explanation.title,
                    explanation.safety_tier.value,
                    explanation.summary,
                    " | ".join(explanation.why_points)
                ])
        except Exception as e:
            print(f"[WARN] Failed to write to {self.csv_path}: {e}")

    def get_recent(
        self,
        limit: int = 25,
        agent: Optional[AgentType] = None,
        decision_type: Optional[str] = None
    ) -> List[DecisionExplanation]:
        """Retrieves filtered explanations from in-memory archive."""
        results = self.memory_buffer
        if agent:
            results = [e for e in results if e.origin_agent == agent or agent in e.participating_agents]
        if decision_type:
            results = [e for e in results if e.decision_type.upper() == decision_type.upper()]
        return results[:limit]

