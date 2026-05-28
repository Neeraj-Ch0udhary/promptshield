"""
LLMGuard — Audit Trail Module
Logs every LLM call with full metadata for compliance and debugging.
Drop this into your existing LLMGuard project.
"""

import json
import uuid
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent / "audit_logs.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the audit log table if it doesn't exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id              TEXT PRIMARY KEY,
                timestamp       TEXT NOT NULL,
                customer_id     TEXT NOT NULL,
                session_id      TEXT,
                model_used      TEXT,
                user_input      TEXT,
                llm_response    TEXT,
                injection_blocked   INTEGER DEFAULT 0,
                injection_confidence REAL,
                hallucination_flagged INTEGER DEFAULT 0,
                hallucination_confidence REAL,
                safe_response   TEXT,
                latency_ms      INTEGER,
                tokens_used     INTEGER,
                flag_reason     TEXT,
                metadata        TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_customer_id ON audit_logs(customer_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp)
        """)
        conn.commit()


class AuditTrail:
    """
    Logs every LLM call for compliance, debugging, and billing.

    Usage:
        audit = AuditTrail(customer_id="acme_corp")
        log_id = audit.log(
            user_input="What is the refund policy?",
            llm_response="Refunds take 5-7 days.",
            guard_result={...},  # result from guard.run()
            model_used="gpt-4o",
            latency_ms=320
        )
    """

    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        init_db()

    def log(
        self,
        user_input: str,
        llm_response: str,
        guard_result: dict,
        model_used: str = "unknown",
        session_id: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Log a single LLM call. Returns the log ID.

        guard_result is the dict returned by guard.run() or guard.check_input() / check_output()
        """
        log_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        injection_blocked = int(guard_result.get("blocked", False))
        injection_confidence = guard_result.get("confidence") if injection_blocked else None

        hallucination_flagged = int(guard_result.get("flagged", False))
        hallucination_confidence = guard_result.get("confidence") if hallucination_flagged else None

        safe_response = guard_result.get("safe_response")

        flag_reason = None
        if injection_blocked:
            flag_reason = "PROMPT_INJECTION"
        elif hallucination_flagged:
            flag_reason = "HALLUCINATION"

        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs (
                    id, timestamp, customer_id, session_id, model_used,
                    user_input, llm_response,
                    injection_blocked, injection_confidence,
                    hallucination_flagged, hallucination_confidence,
                    safe_response, latency_ms, tokens_used,
                    flag_reason, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id, timestamp, self.customer_id, session_id, model_used,
                user_input, llm_response,
                injection_blocked, injection_confidence,
                hallucination_flagged, hallucination_confidence,
                safe_response, latency_ms, tokens_used,
                flag_reason,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()

        return log_id

    def get_logs(
        self,
        limit: int = 100,
        flagged_only: bool = False,
        session_id: Optional[str] = None,
    ) -> list[dict]:
        """Retrieve logs for this customer."""
        query = "SELECT * FROM audit_logs WHERE customer_id = ?"
        params: list = [self.customer_id]

        if flagged_only:
            query += " AND (injection_blocked = 1 OR hallucination_flagged = 1)"

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with _get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_summary(self) -> dict:
        """Get compliance summary stats for this customer."""
        with _get_connection() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_calls,
                    SUM(injection_blocked) as injections_blocked,
                    SUM(hallucination_flagged) as hallucinations_caught,
                    ROUND(AVG(latency_ms), 1) as avg_latency_ms,
                    SUM(tokens_used) as total_tokens,
                    MIN(timestamp) as first_call,
                    MAX(timestamp) as last_call
                FROM audit_logs
                WHERE customer_id = ?
            """, (self.customer_id,)).fetchone()

            return dict(row)


# ── FastAPI routes — drop these into your existing api/ folder ──────────────

def register_audit_routes(app, require_api_key=None):
    """
    Register audit trail endpoints onto your existing FastAPI app.

    Usage in your api/main.py:
        from audit_trail import register_audit_routes
        register_audit_routes(app)
    """
    from fastapi import HTTPException, Query

    @app.get("/audit/logs")
    def get_audit_logs(
        customer_id: str = Query(...),
        limit: int = Query(100, le=1000),
        flagged_only: bool = Query(False),
        session_id: Optional[str] = Query(None),
    ):
        """Get all audit logs for a customer."""
        audit = AuditTrail(customer_id=customer_id)
        logs = audit.get_logs(limit=limit, flagged_only=flagged_only, session_id=session_id)
        return {"customer_id": customer_id, "count": len(logs), "logs": logs}

    @app.get("/audit/summary")
    def get_audit_summary(customer_id: str = Query(...)):
        """Get compliance summary for a customer."""
        audit = AuditTrail(customer_id=customer_id)
        summary = audit.get_summary()
        return {"customer_id": customer_id, "summary": summary}