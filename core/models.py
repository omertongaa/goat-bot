"""Pure data models for the goat control plane.

Dataclasses here mirror Paperclip's entity vocabulary so future UI work has a
familiar mental model. All fields are JSON-serializable primitives — no Python
objects in nested state.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import uuid


def now_iso() -> str:
    """UTC ISO-8601 timestamp with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── Status enums (strings for easy JSON + frontend) ────────────────

TICKET_STATUSES = (
    "pending",          # created, not picked up yet
    "in_progress",      # agent executing
    "needs_review",     # result ready, awaiting approval
    "approved",         # approved, action may fire (e.g. outreach send)
    "completed",        # terminal success
    "failed",           # terminal error
    "paused_budget",    # blocked by budget hard-stop
    "paused_manual",    # user paused
    "cancelled",        # user cancelled
)

GOAL_STATUSES = ("active", "achieved", "archived")


# ── Entities ───────────────────────────────────────────────────────

@dataclass
class Company:
    id: str
    name: str
    mission: str = ""
    owner_name: str = ""
    niche: str = ""
    target_cities: list = field(default_factory=list)
    target_industries: list = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    # Local API keys — stored here so each company can have its own keychain
    api_keys: dict = field(default_factory=dict)
    # Runtime settings: scraper_actor, email_finder_providers, default_budgets
    settings: dict = field(default_factory=dict)
    # Skills the user has activated (Faz 6)
    skills: list = field(default_factory=list)


@dataclass
class Goal:
    id: str
    company_id: str
    title: str
    description: str = ""
    target_metric: str = ""    # "50 hot leads", "$20K proposal pipeline"
    deadline: Optional[str] = None
    parent_id: Optional[str] = None
    status: str = "active"
    created_at: str = field(default_factory=now_iso)
    achieved_at: Optional[str] = None


@dataclass
class Ticket:
    id: str
    company_id: str
    title: str
    description: str = ""
    agent_id: str = ""
    status: str = "pending"
    goal_id: Optional[str] = None
    parent_ticket_id: Optional[str] = None
    params: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    # Artifacts: [{kind: "proposal_pdf", path: "outputs/...", name: "..."}]
    artifacts: list = field(default_factory=list)
    cost_usd: float = 0.0
    cost_breakdown: dict = field(default_factory=dict)
    # Approval gate: if True, agent outputs result but doesn't execute side effects
    # until approved_by is set
    needs_approval: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    # Lifecycle timestamps
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    # Freeform error message if status == "failed"
    error: Optional[str] = None


@dataclass
class Budget:
    """Monthly USD budget per (company, agent) pair. Hard-stop when spent >= amount."""
    company_id: str
    agent_id: str
    amount_usd: float
    period: str = "monthly"
    current_period_start: str = field(default_factory=now_iso)
    spent_usd: float = 0.0


@dataclass
class ActivityEntry:
    """One line in the append-only audit log."""
    timestamp: str
    company_id: str
    kind: str        # ticket_created, ticket_completed, budget_exceeded, config_changed, approval_granted, ...
    actor: str       # agent_id | "user" | "system"
    subject: str     # ticket_id | goal_id | budget:{agent_id} | ...
    details: dict = field(default_factory=dict)


# ── Helpers ────────────────────────────────────────────────────────

def to_dict(obj) -> dict:
    """Dataclass → JSON-friendly dict."""
    return asdict(obj)
