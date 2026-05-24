"""
Tenant Manager — Multi-tenant Lifecycle Management
====================================================
Manages tenant provisioning, quotas, and isolation.
Uses SQLite for persistence and in-memory dict for rate limiting.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid
import json
import os
import sqlite3
import threading
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("TENANT_DB_PATH", "/app/src/ai_os/data/tenants.db")


# ---------------------------------------------------------------------------
# Thread-safe SQLite helper
# ---------------------------------------------------------------------------

_db_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _db_lock:
        conn = _get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                plan TEXT DEFAULT 'free',
                max_agents INTEGER DEFAULT 5,
                max_workflows INTEGER DEFAULT 50,
                max_executions_per_day INTEGER DEFAULT 1000,
                max_concurrent_executions INTEGER DEFAULT 5,
                max_storage_mb INTEGER DEFAULT 1000,
                max_api_calls_per_minute INTEGER DEFAULT 60,
                status TEXT DEFAULT 'active',
                is_trial INTEGER DEFAULT 0,
                trial_ends_at TEXT,
                stripe_customer_id TEXT,
                billing_email TEXT DEFAULT '',
                settings TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                settings TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT DEFAULT '',
                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS usage_daily (
                tenant_id TEXT NOT NULL,
                resource TEXT NOT NULL,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (tenant_id, resource, date)
            );
        """)
        conn.commit()
        conn.close()


_init_db()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class Tenant:
    id: str
    name: str
    slug: str
    plan: str = "free"
    max_agents: int = 5
    max_workflows: int = 50
    max_executions_per_day: int = 1000
    max_concurrent_executions: int = 5
    max_storage_mb: int = 1000
    max_api_calls_per_minute: int = 60
    status: str = "active"
    is_trial: bool = False
    trial_ends_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    billing_email: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_trial_expired(self) -> bool:
        if self.is_trial and self.trial_ends_at:
            return datetime.now() > self.trial_ends_at
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "plan": self.plan,
            "status": self.status,
            "is_trial": self.is_trial,
            "settings": self.settings,
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def from_row(row) -> "Tenant":
        return Tenant(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            plan=row["plan"],
            max_agents=row["max_agents"],
            max_workflows=row["max_workflows"],
            max_executions_per_day=row["max_executions_per_day"],
            max_concurrent_executions=row["max_concurrent_executions"],
            max_storage_mb=row["max_storage_mb"],
            max_api_calls_per_minute=row["max_api_calls_per_minute"],
            status=row["status"],
            is_trial=bool(row["is_trial"]),
            trial_ends_at=datetime.fromisoformat(row["trial_ends_at"]) if row["trial_ends_at"] else None,
            stripe_customer_id=row["stripe_customer_id"],
            billing_email=row["billing_email"] or "",
            settings=json.loads(row["settings"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


@dataclass
class Workspace:
    id: str
    tenant_id: str
    name: str
    slug: str
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""

    @property
    def is_active(self) -> bool:
        return True

    @staticmethod
    def from_row(row) -> "Workspace":
        return Workspace(
            id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            slug=row["slug"],
            settings=json.loads(row["settings"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            created_by=row["created_by"] or "",
        )


# ---------------------------------------------------------------------------
# TenantManager
# ---------------------------------------------------------------------------

class TenantManager:
    """
    Manages tenant lifecycle and isolation.
    Persists to SQLite. Uses in-memory counters for per-minute rate limits.
    """

    def __init__(self, db=None, cache=None):
        self._rate_counters: Dict[str, List[datetime]] = {}  # tenant:resource -> timestamps

    # -------------------------------------------------------------------------
    # TENANT OPERATIONS
    # -------------------------------------------------------------------------

    async def create_tenant(
        self,
        name: str,
        email: str,
        plan: str = "free",
        settings: Dict[str, Any] = None,
    ) -> Tenant:
        slug = self._generate_slug(name)
        now = datetime.now().isoformat()
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            plan=plan,
            billing_email=email,
            settings=settings or {},
        )
        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("""
                    INSERT INTO tenants
                    (id, name, slug, plan, max_agents, max_workflows,
                     max_executions_per_day, max_concurrent_executions,
                     max_storage_mb, max_api_calls_per_minute, status,
                     is_trial, billing_email, settings, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    tenant.id, tenant.name, tenant.slug, tenant.plan,
                    tenant.max_agents, tenant.max_workflows,
                    tenant.max_executions_per_day, tenant.max_concurrent_executions,
                    tenant.max_storage_mb, tenant.max_api_calls_per_minute,
                    tenant.status, int(tenant.is_trial), tenant.billing_email,
                    json.dumps(tenant.settings), now, now
                ))
                conn.commit()
            finally:
                conn.close()
        logger.info(f"Created tenant: {tenant.id} ({tenant.name})")
        return tenant

    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        with _db_lock:
            conn = _get_conn()
            try:
                row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
                return Tenant.from_row(row) if row else None
            finally:
                conn.close()

    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        with _db_lock:
            conn = _get_conn()
            try:
                row = conn.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
                return Tenant.from_row(row) if row else None
            finally:
                conn.close()

    async def update_tenant(self, tenant_id: str, **updates) -> Optional[Tenant]:
        allowed = {"name", "plan", "status", "billing_email", "settings",
                   "max_agents", "max_workflows", "stripe_customer_id"}
        safe = {k: v for k, v in updates.items() if k in allowed}
        if not safe:
            return await self.get_tenant(tenant_id)

        if "settings" in safe:
            safe["settings"] = json.dumps(safe["settings"])

        safe["updated_at"] = datetime.now().isoformat()
        fields = ", ".join(f"{k} = ?" for k in safe)
        values = list(safe.values()) + [tenant_id]

        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute(f"UPDATE tenants SET {fields} WHERE id = ?", values)
                conn.commit()
            finally:
                conn.close()
        return await self.get_tenant(tenant_id)

    async def delete_tenant(self, tenant_id: str) -> bool:
        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("DELETE FROM workspaces WHERE tenant_id = ?", (tenant_id,))
                conn.execute("DELETE FROM usage_daily WHERE tenant_id = ?", (tenant_id,))
                conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
                conn.commit()
                logger.info(f"Deleted tenant: {tenant_id}")
                return True
            except Exception as e:
                logger.error(f"Delete tenant failed: {e}")
                return False
            finally:
                conn.close()

    # -------------------------------------------------------------------------
    # WORKSPACE OPERATIONS
    # -------------------------------------------------------------------------

    async def create_workspace(
        self,
        tenant_id: str,
        name: str,
        created_by: str = "",
        settings: Dict[str, Any] = None,
    ) -> Workspace:
        slug = self._generate_slug(name)
        now = datetime.now().isoformat()
        workspace = Workspace(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            settings=settings or {},
            created_by=created_by,
        )
        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("""
                    INSERT INTO workspaces (id, tenant_id, name, slug, settings, created_at, updated_at, created_by)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (workspace.id, tenant_id, name, slug, json.dumps(workspace.settings), now, now, created_by))
                conn.commit()
            finally:
                conn.close()
        return workspace

    async def get_workspace(self, workspace_id: str, tenant_id: str) -> Optional[Workspace]:
        with _db_lock:
            conn = _get_conn()
            try:
                row = conn.execute(
                    "SELECT * FROM workspaces WHERE id = ? AND tenant_id = ?",
                    (workspace_id, tenant_id)
                ).fetchone()
                return Workspace.from_row(row) if row else None
            finally:
                conn.close()

    async def list_workspaces(self, tenant_id: str) -> List[Workspace]:
        with _db_lock:
            conn = _get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM workspaces WHERE tenant_id = ?", (tenant_id,)
                ).fetchall()
                return [Workspace.from_row(r) for r in rows]
            finally:
                conn.close()

    async def delete_workspace(self, workspace_id: str, tenant_id: str) -> bool:
        with _db_lock:
            conn = _get_conn()
            try:
                result = conn.execute(
                    "DELETE FROM workspaces WHERE id = ? AND tenant_id = ?",
                    (workspace_id, tenant_id)
                )
                conn.commit()
                return result.rowcount > 0
            finally:
                conn.close()

    # -------------------------------------------------------------------------
    # QUOTA MANAGEMENT
    # -------------------------------------------------------------------------

    async def check_quota(self, tenant_id: str, resource: str, increment: int = 1) -> bool:
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False

        usage = await self._get_usage(tenant_id, resource)
        limits = {
            "agents": tenant.max_agents,
            "workflows": tenant.max_workflows,
            "executions": tenant.max_executions_per_day,
            "concurrent_executions": tenant.max_concurrent_executions,
            "storage_mb": tenant.max_storage_mb,
            "api_calls_per_minute": tenant.max_api_calls_per_minute,
        }
        limit = limits.get(resource, -1)
        if limit == -1:
            return True
        return usage + increment <= limit

    async def increment_usage(self, tenant_id: str, resource: str, amount: int = 1) -> None:
        # Per-minute rate limiting — use in-memory sliding window
        if resource == "api_calls_per_minute":
            key = f"{tenant_id}:{resource}"
            now = datetime.now()
            window = now - timedelta(minutes=1)
            timestamps = self._rate_counters.get(key, [])
            timestamps = [t for t in timestamps if t > window]
            timestamps.extend([now] * amount)
            self._rate_counters[key] = timestamps
            return

        # Daily counters — persist to SQLite
        today = datetime.now().strftime("%Y-%m-%d")
        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute("""
                    INSERT INTO usage_daily (tenant_id, resource, date, count)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(tenant_id, resource, date) DO UPDATE SET count = count + ?
                """, (tenant_id, resource, today, amount, amount))
                conn.commit()
            finally:
                conn.close()

    async def get_usage_summary(self, tenant_id: str) -> Dict[str, Any]:
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return {}

        today = datetime.now().strftime("%Y-%m-%d")
        with _db_lock:
            conn = _get_conn()
            try:
                rows = conn.execute(
                    "SELECT resource, count FROM usage_daily WHERE tenant_id = ? AND date = ?",
                    (tenant_id, today)
                ).fetchall()
                daily = {r["resource"]: r["count"] for r in rows}
            finally:
                conn.close()

        # Per-minute usage from memory
        minute_key = f"{tenant_id}:api_calls_per_minute"
        now = datetime.now()
        window = now - timedelta(minutes=1)
        minute_count = len([t for t in self._rate_counters.get(minute_key, []) if t > window])

        return {
            "agents": {"used": daily.get("agents", 0), "limit": tenant.max_agents},
            "workflows": {"used": daily.get("workflows", 0), "limit": tenant.max_workflows},
            "executions_today": {"used": daily.get("executions", 0), "limit": tenant.max_executions_per_day},
            "concurrent_executions": {"used": daily.get("concurrent_executions", 0), "limit": tenant.max_concurrent_executions},
            "storage_mb": {"used": daily.get("storage_mb", 0), "limit": tenant.max_storage_mb},
            "api_calls_minute": {"used": minute_count, "limit": tenant.max_api_calls_per_minute},
        }

    # -------------------------------------------------------------------------
    # PLAN MANAGEMENT
    # -------------------------------------------------------------------------

    async def change_plan(self, tenant_id: str, new_plan: str) -> Optional[Tenant]:
        plan_limits = {
            "free": {"max_agents": 5, "max_workflows": 50, "max_executions_per_day": 1000},
            "pro": {"max_agents": 20, "max_workflows": 500, "max_executions_per_day": 10000},
            "enterprise": {"max_agents": 999, "max_workflows": 9999, "max_executions_per_day": 999999},
        }
        limits = plan_limits.get(new_plan, plan_limits["free"])
        return await self.update_tenant(tenant_id, plan=new_plan, **limits)

    async def start_trial(self, tenant_id: str) -> Optional[datetime]:
        trial_end = datetime.now() + timedelta(days=14)
        with _db_lock:
            conn = _get_conn()
            try:
                conn.execute(
                    "UPDATE tenants SET is_trial = 1, trial_ends_at = ?, plan = 'pro', updated_at = ? WHERE id = ?",
                    (trial_end.isoformat(), datetime.now().isoformat(), tenant_id)
                )
                conn.commit()
            finally:
                conn.close()
        logger.info(f"Trial started for tenant {tenant_id} until {trial_end}")
        return trial_end

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------

    def _generate_slug(self, name: str) -> str:
        import re
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug

    async def _get_usage(self, tenant_id: str, resource: str) -> int:
        if resource == "api_calls_per_minute":
            key = f"{tenant_id}:{resource}"
            now = datetime.now()
            window = now - timedelta(minutes=1)
            return len([t for t in self._rate_counters.get(key, []) if t > window])

        today = datetime.now().strftime("%Y-%m-%d")
        with _db_lock:
            conn = _get_conn()
            try:
                row = conn.execute(
                    "SELECT count FROM usage_daily WHERE tenant_id = ? AND resource = ? AND date = ?",
                    (tenant_id, resource, today)
                ).fetchone()
                return row["count"] if row else 0
            finally:
                conn.close()

    async def get_context(self, tenant_id: str, user_id: str, workspace_id: str = None):
        from ..tenant.context import TenantContext, TenantQuota
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")
        if not workspace_id:
            workspaces = await self.list_workspaces(tenant_id)
            if workspaces:
                workspace_id = workspaces[0].id
        return TenantContext(
            tenant_id=tenant_id,
            workspace_id=workspace_id or "",
            user_id=user_id,
            plan=tenant.plan,
            quota=TenantQuota.for_plan(tenant.plan),
        )


# -------------------------------------------------------------------------
# QUOTA ENFORCEMENT
# -------------------------------------------------------------------------

class QuotaExceededError(Exception):
    def __init__(self, resource: str, limit: int):
        self.resource = resource
        self.limit = limit
        super().__init__(f"Quota exceeded for {resource}. Limit: {limit}")


async def enforce_quota(tenant_manager: TenantManager, tenant_id: str, resource: str) -> None:
    allowed = await tenant_manager.check_quota(tenant_id, resource)
    if not allowed:
        tenant = await tenant_manager.get_tenant(tenant_id)
        limit = getattr(tenant, f"max_{resource}", 0)
        raise QuotaExceededError(resource, limit)
