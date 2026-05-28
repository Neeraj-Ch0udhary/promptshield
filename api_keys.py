"""
PromptShield — API Keys & Multi-tenancy Module
Each customer gets their own API key, isolated data, and usage tracking.
Drop this into your project root alongside audit_trail.py
"""

import secrets
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "audit_logs.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_keys_db():
    """Create the API keys table if it doesn't exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id     TEXT NOT NULL UNIQUE,
                customer_name   TEXT NOT NULL,
                key_hash        TEXT NOT NULL UNIQUE,
                key_prefix      TEXT NOT NULL,
                plan            TEXT DEFAULT 'free',
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT NOT NULL,
                last_used_at    TEXT,
                monthly_limit   INTEGER DEFAULT 1000,
                calls_this_month INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_key_hash ON api_keys(key_hash)
        """)
        conn.commit()


class APIKeyManager:
    """
    Manages API keys for all customers.

    Usage:
        manager = APIKeyManager()

        # Create a new customer key
        key = manager.create_key("acme_corp", "Acme Corporation", plan="pro")
        print(key)  # ps_live_abc123... (show once, never stored)

        # Validate on every API request
        customer = manager.validate_key("ps_live_abc123...")
        if not customer:
            raise HTTPException(401, "Invalid API key")
    """

    def __init__(self):
        init_keys_db()

    def create_key(
        self,
        customer_id: str,
        customer_name: str,
        plan: str = "free",
        monthly_limit: int = 1000,
    ) -> str:
        """
        Generate a new API key for a customer.
        Returns the FULL key — show it once, never store it.
        """
        raw_key = f"ps_live_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:16]
        created_at = datetime.now(timezone.utc).isoformat()

        with _get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO api_keys
                (customer_id, customer_name, key_hash, key_prefix, plan,
                 is_active, created_at, monthly_limit, calls_this_month)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, 0)
            """, (customer_id, customer_name, key_hash, key_prefix,
                  plan, created_at, monthly_limit))
            conn.commit()

        return raw_key

    def validate_key(self, raw_key: str) -> Optional[dict]:
        """
        Validate an API key on every request.
        Returns customer info dict if valid, None if invalid/inactive/over limit.
        """
        if not raw_key or not raw_key.startswith("ps_live_"):
            return None

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        with _get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1
            """, (key_hash,)).fetchone()

            if not row:
                return None

            customer = dict(row)

            # Check monthly limit
            if customer["calls_this_month"] >= customer["monthly_limit"]:
                return None

            # Update last used + increment call count
            conn.execute("""
                UPDATE api_keys
                SET last_used_at = ?, calls_this_month = calls_this_month + 1
                WHERE key_hash = ?
            """, (datetime.now(timezone.utc).isoformat(), key_hash))
            conn.commit()

        return customer

    def revoke_key(self, customer_id: str) -> bool:
        """Deactivate a customer's API key."""
        with _get_connection() as conn:
            result = conn.execute("""
                UPDATE api_keys SET is_active = 0 WHERE customer_id = ?
            """, (customer_id,))
            conn.commit()
            return result.rowcount > 0

    def get_usage(self, customer_id: str) -> Optional[dict]:
        """Get usage stats for a customer."""
        with _get_connection() as conn:
            row = conn.execute("""
                SELECT customer_id, customer_name, plan, is_active,
                       calls_this_month, monthly_limit, last_used_at, created_at
                FROM api_keys WHERE customer_id = ?
            """, (customer_id,)).fetchone()
            return dict(row) if row else None

    def list_customers(self) -> list[dict]:
        """List all customers (admin use)."""
        with _get_connection() as conn:
            rows = conn.execute("""
                SELECT customer_id, customer_name, plan, is_active,
                       key_prefix, calls_this_month, monthly_limit,
                       created_at, last_used_at
                FROM api_keys ORDER BY created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def reset_monthly_counts(self):
        """Call this on the 1st of each month (cron job)."""
        with _get_connection() as conn:
            conn.execute("UPDATE api_keys SET calls_this_month = 0")
            conn.commit()


# ── FastAPI middleware — drop into your existing api/ folder ─────────────────

def register_key_routes(app):
    """
    Register API key management endpoints onto your existing FastAPI app.

    Usage in your api/main.py:
        from api_keys import register_key_routes, require_api_key
        register_key_routes(app)

        # Then protect any route:
        @app.post("/check/input")
        def check_input(body: dict, customer=Depends(require_api_key)):
            ...
    """
    from fastapi import HTTPException
    from pydantic import BaseModel

    manager = APIKeyManager()

    class CreateKeyRequest(BaseModel):
        customer_id: str
        customer_name: str
        plan: str = "free"
        monthly_limit: int = 1000

    @app.post("/admin/keys/create")
    def create_api_key(req: CreateKeyRequest):
        """Admin: create a new customer API key."""
        key = manager.create_key(
            req.customer_id, req.customer_name,
            req.plan, req.monthly_limit
        )
        return {
            "customer_id": req.customer_id,
            "api_key": key,
            "warning": "Save this key now — it will never be shown again."
        }

    @app.post("/admin/keys/revoke/{customer_id}")
    def revoke_api_key(customer_id: str):
        """Admin: revoke a customer's API key."""
        success = manager.revoke_key(customer_id)
        if not success:
            raise HTTPException(404, "Customer not found")
        return {"revoked": True, "customer_id": customer_id}

    @app.get("/admin/keys")
    def list_all_customers():
        """Admin: list all customers and usage."""
        return {"customers": manager.list_customers()}

    @app.get("/usage")
    def get_my_usage(customer_id: str):
        """Customer: get their own usage stats."""
        usage = manager.get_usage(customer_id)
        if not usage:
            raise HTTPException(404, "Customer not found")
        return usage


def require_api_key(authorization: str = None):
    """
    FastAPI dependency — protects any route with API key auth.

    Usage:
        from fastapi import Depends
        from api_keys import require_api_key

        @app.post("/check/input")
        def check_input(body: dict, customer=Depends(require_api_key)):
            audit = AuditTrail(customer_id=customer["customer_id"])
            ...
    """
    from fastapi import Header, HTTPException

    manager = APIKeyManager()

    def _require(authorization: Optional[str] = Header(None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing API key. Use: Authorization: Bearer ps_live_...")
        raw_key = authorization.replace("Bearer ", "")
        customer = manager.validate_key(raw_key)
        if not customer:
            raise HTTPException(401, "Invalid, inactive, or rate-limited API key.")
        return customer

    return _require