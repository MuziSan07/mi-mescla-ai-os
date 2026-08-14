"""
AI-OS Tenant Manager — SQLite-backed, SQL-injection-safe UPDATE.

Security fix: column names in UPDATE are validated against an explicit
allowlist before string-interpolation. All values use parameterised bindings.
"""

import sqlite3, os, uuid, logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
DB_PATH = os.getenv("TENANT_DB_PATH", "/app/src/ai_os/data/tenants.db")

_UPDATABLE_TENANT_COLUMNS = frozenset({
    "name","slug","is_active","plan","max_executions_per_day","max_concurrent_executions","metadata"
})


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1, plan TEXT DEFAULT 'free',
            max_executions_per_day INTEGER DEFAULT 1000,
            max_concurrent_executions INTEGER DEFAULT 5,
            created_at TEXT NOT NULL, metadata TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage_daily (
            tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            date TEXT NOT NULL, executions INTEGER DEFAULT 0,
            concurrent_executions INTEGER DEFAULT 0, PRIMARY KEY (tenant_id, date)
        );
    """)
    conn.commit()


@dataclass
class Tenant:
    id: str; name: str; slug: str; is_active: bool = True; plan: str = "free"
    max_executions_per_day: int = 1000; max_concurrent_executions: int = 5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: str = "{}"


def _row_to_tenant(row: sqlite3.Row) -> Tenant:
    return Tenant(id=row["id"], name=row["name"], slug=row["slug"],
                  is_active=bool(row["is_active"]), plan=row["plan"],
                  max_executions_per_day=row["max_executions_per_day"],
                  max_concurrent_executions=row["max_concurrent_executions"],
                  created_at=row["created_at"], metadata=row.get("metadata","{}"))


class TenantManager:
    def __init__(self):
        with _get_conn() as conn: _init_db(conn)

    def create_tenant(self, name: str, slug: str, plan: str = "free") -> Tenant:
        t = Tenant(id=str(uuid.uuid4()), name=name, slug=slug, plan=plan)
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO tenants (id,name,slug,is_active,plan,max_executions_per_day,"
                "max_concurrent_executions,created_at,metadata) VALUES (?,?,?,?,?,?,?,?,?)",
                (t.id,t.name,t.slug,int(t.is_active),t.plan,t.max_executions_per_day,
                 t.max_concurrent_executions,t.created_at,t.metadata))
            conn.commit()
        return t

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        return _row_to_tenant(row) if row else None

    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
        return _row_to_tenant(row) if row else None

    def list_tenants(self, active_only: bool = False) -> List[Tenant]:
        q = "SELECT * FROM tenants" + (" WHERE is_active = 1" if active_only else "")
        with _get_conn() as conn:
            return [_row_to_tenant(r) for r in conn.execute(q).fetchall()]

    def update_tenant(self, tenant_id: str, updates: Dict[str, Any]) -> Optional[Tenant]:
        """
        Update tenant fields. Column names validated against allowlist before
        interpolation — values always use parameterised placeholders.
        """
        if not updates: return self.get_tenant(tenant_id)
        invalid = set(updates.keys()) - _UPDATABLE_TENANT_COLUMNS
        if invalid:
            raise ValueError(f"Column(s) not in update allowlist: {invalid}. Allowed: {sorted(_UPDATABLE_TENANT_COLUMNS)}")
        set_clause = ", ".join(f"{col} = ?" for col in updates.keys())
        values = list(updates.values()) + [tenant_id]
        with _get_conn() as conn:
            conn.execute(f"UPDATE tenants SET {set_clause} WHERE id = ?", values)
            conn.commit()
            row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        return _row_to_tenant(row) if row else None

    def delete_tenant(self, tenant_id: str) -> bool:
        with _get_conn() as conn:
            conn.execute("DELETE FROM workspaces WHERE tenant_id = ?", (tenant_id,))
            conn.execute("DELETE FROM usage_daily WHERE tenant_id = ?", (tenant_id,))
            cur = conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
            conn.commit()
            return cur.rowcount > 0

    def record_execution(self, tenant_id: str, concurrent: int = 1) -> bool:
        t = self.get_tenant(tenant_id)
        if not t or not t.is_active: return False
        today = datetime.now(timezone.utc).date().isoformat()
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO usage_daily (tenant_id,date,executions,concurrent_executions) VALUES (?,?,1,?) "
                "ON CONFLICT(tenant_id,date) DO UPDATE SET executions=executions+1, "
                "concurrent_executions=MAX(concurrent_executions,excluded.concurrent_executions)",
                (tenant_id, today, concurrent))
            conn.commit()
            row = conn.execute("SELECT executions FROM usage_daily WHERE tenant_id=? AND date=?",
                               (tenant_id, today)).fetchone()
        if row and row["executions"] > t.max_executions_per_day:
            logger.warning("Tenant %s exceeded daily limit", tenant_id)
            return False
        return True

    def get_usage(self, tenant_id: str) -> Dict[str, Any]:
        t = self.get_tenant(tenant_id)
        if not t: return {}
        today = datetime.now(timezone.utc).date().isoformat()
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM usage_daily WHERE tenant_id=? AND date=?",
                               (tenant_id, today)).fetchone()
        daily = dict(row) if row else {}
        return {"tenant_id": tenant_id, "plan": t.plan,
                "limits": {"executions": t.max_executions_per_day, "concurrent_executions": t.max_concurrent_executions},
                "today": {"executions_used": daily.get("executions",0), "concurrent_peak": daily.get("concurrent_executions",0)}}


_tenant_manager: Optional[TenantManager] = None

def get_tenant_manager() -> TenantManager:
    global _tenant_manager
    if _tenant_manager is None: _tenant_manager = TenantManager()
    return _tenant_manager
