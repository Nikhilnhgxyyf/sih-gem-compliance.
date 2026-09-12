"""SQLite persistence adapter for audit state; compliance logic stays in the engine."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine import ProcurementIntelligenceEngine
from schemas import AuditEvent, EvidenceNode, RuleEvaluation, RuleNode


class SQLiteAuditStore:
    """Small, deterministic persistence adapter suitable for the prototype."""

    def __init__(self, database_path: Optional[str] = None):
        configured = database_path or os.environ.get("AUDIT_DB_PATH")
        self.database_path = configured or str(Path(__file__).parent / "data" / "gem_audit.db")
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS audit_sessions (
                    audit_id TEXT PRIMARY KEY, bidder_id TEXT NOT NULL, bidder_label TEXT NOT NULL,
                    tender_id TEXT, tender_version TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    evaluation_timestamp TEXT NOT NULL, status TEXT NOT NULL, snapshot_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    audit_id TEXT NOT NULL, evidence_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                    temporal_state TEXT NOT NULL, evidence_fingerprint TEXT, PRIMARY KEY (audit_id, evidence_id)
                );
                CREATE TABLE IF NOT EXISTS rules (
                    audit_id TEXT NOT NULL, rule_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                    PRIMARY KEY (audit_id, rule_id)
                );
                CREATE TABLE IF NOT EXISTS rule_evaluations (
                    audit_id TEXT NOT NULL, rule_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                    PRIMARY KEY (audit_id, rule_id)
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    audit_id TEXT PRIMARY KEY, decision_json TEXT NOT NULL, decision_dna_json TEXT NOT NULL,
                    decision_fingerprint TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    audit_id TEXT NOT NULL, event_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                    PRIMARY KEY (audit_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS simulations (
                    simulation_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decision_capsules (
                    audit_id TEXT PRIMARY KEY, capsule_json TEXT NOT NULL, capsule_fingerprint TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    def save_engine(self, engine: ProcurementIntelligenceEngine, bidder_id: str, bidder_label: str,
                    tender_id: Optional[str] = None, tender_version: Optional[str] = None,
                    status: str = "ACTIVE") -> None:
        """Persist calculated state after an engine mutation, without reimplementing rules in SQL."""
        evaluations = engine.evaluate_all_rules()
        decision = engine.calculate_overall_compliance(evaluations).model_dump(mode="json")
        decision_dna = engine.decision_dna()
        now = datetime.now(timezone.utc).isoformat()
        snapshot = {
            "audit_id": engine.audit_id, "tender_deadline": engine.tender_deadline.isoformat(),
            "evaluation_timestamp": engine.evaluation_timestamp.isoformat(), "engine_version": engine.engine_version,
            "evidence": [node.model_dump(mode="json") for node in engine.evidence_nodes.values()],
            "rules": [rule.model_dump(mode="json") for rule in engine.rule_nodes.values()],
            "evaluations": {rule_id: evaluation.model_dump(mode="json") for rule_id, evaluation in evaluations.items()},
            "ledger": [event.model_dump(mode="json") for event in engine.ledger],
        }
        with self._connect() as connection:
            connection.execute("""INSERT INTO audit_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(audit_id) DO UPDATE SET bidder_id=excluded.bidder_id, bidder_label=excluded.bidder_label,
                tender_id=excluded.tender_id, tender_version=excluded.tender_version, updated_at=excluded.updated_at,
                evaluation_timestamp=excluded.evaluation_timestamp, status=excluded.status, snapshot_json=excluded.snapshot_json""",
                (engine.audit_id, bidder_id, bidder_label, tender_id, tender_version, now, now,
                 engine.evaluation_timestamp.isoformat(), status, self._dump(snapshot)))
            connection.execute("DELETE FROM evidence WHERE audit_id = ?", (engine.audit_id,))
            connection.execute("DELETE FROM rules WHERE audit_id = ?", (engine.audit_id,))
            connection.execute("DELETE FROM rule_evaluations WHERE audit_id = ?", (engine.audit_id,))
            connection.execute("DELETE FROM audit_events WHERE audit_id = ?", (engine.audit_id,))
            connection.executemany("INSERT INTO evidence VALUES (?, ?, ?, ?, ?)", [
                (engine.audit_id, evidence_id, self._dump(node.model_dump(mode="json")), engine.temporal_state(node).value,
                 engine.evidence_fingerprint(node)) for evidence_id, node in engine.evidence_nodes.items()])
            connection.executemany("INSERT INTO rules VALUES (?, ?, ?)", [
                (engine.audit_id, rule_id, self._dump(rule.model_dump(mode="json"))) for rule_id, rule in engine.rule_nodes.items()])
            connection.executemany("INSERT INTO rule_evaluations VALUES (?, ?, ?)", [
                (engine.audit_id, rule_id, self._dump(evaluation.model_dump(mode="json"))) for rule_id, evaluation in evaluations.items()])
            connection.executemany("INSERT INTO audit_events VALUES (?, ?, ?)", [
                (engine.audit_id, event.event_id, self._dump(event.model_dump(mode="json"))) for event in engine.ledger])
            connection.execute("""INSERT INTO decisions VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(audit_id) DO UPDATE SET decision_json=excluded.decision_json,
                decision_dna_json=excluded.decision_dna_json, decision_fingerprint=excluded.decision_fingerprint,
                updated_at=excluded.updated_at""", (engine.audit_id, self._dump(decision), self._dump(decision_dna),
                decision_dna["decision_fingerprint"], now))

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM audit_sessions ORDER BY updated_at DESC")]

    def latest_active(self) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute("SELECT audit_id FROM audit_sessions WHERE status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1").fetchone()
        return self.load_engine(row["audit_id"]) if row else None

    def deactivate_all(self) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE audit_sessions SET status = 'RESET', updated_at = ? WHERE status = 'ACTIVE'",
                               (datetime.now(timezone.utc).isoformat(),))

    def load_engine(self, audit_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            session = connection.execute("SELECT * FROM audit_sessions WHERE audit_id = ?", (audit_id,)).fetchone()
        if not session:
            return None
        snapshot = json.loads(session["snapshot_json"])
        engine = ProcurementIntelligenceEngine(audit_id, datetime.fromisoformat(snapshot["tender_deadline"]))
        engine.evaluation_timestamp = datetime.fromisoformat(snapshot["evaluation_timestamp"])
        engine.engine_version = snapshot.get("engine_version", engine.engine_version)
        engine.ledger = []
        for payload in snapshot["evidence"]:
            engine.register_evidence(EvidenceNode.model_validate(payload))
        for payload in snapshot["rules"]:
            engine.register_rule(RuleNode.model_validate(payload))
        engine.rebuild_dependencies()
        engine.current_rule_evaluations = {rule_id: RuleEvaluation.model_validate(payload)
                                           for rule_id, payload in snapshot.get("evaluations", {}).items()}
        engine.current_rule_states = {rule_id: evaluation.status for rule_id, evaluation in engine.current_rule_evaluations.items()}
        engine.ledger = [AuditEvent.model_validate(payload) for payload in snapshot.get("ledger", [])]
        return {"engine": engine, "bidder_id": session["bidder_id"], "bidder_label": session["bidder_label"],
                "tender_id": session["tender_id"], "tender_version": session["tender_version"], "status": session["status"]}

    def save_simulation(self, audit_id: str, simulation: Dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO simulations VALUES (?, ?, ?, ?)",
                               (simulation["simulation_id"], audit_id, self._dump(simulation), datetime.now(timezone.utc).isoformat()))

    def save_capsule(self, audit_id: str, capsule: Dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO decision_capsules VALUES (?, ?, ?, ?)",
                               (audit_id, self._dump(capsule), capsule["integrity_metadata"]["capsule_fingerprint"], datetime.now(timezone.utc).isoformat()))

    def load_capsule(self, audit_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute("SELECT capsule_json FROM decision_capsules WHERE audit_id = ?", (audit_id,)).fetchone()
        return json.loads(row["capsule_json"]) if row else None
