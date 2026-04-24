"""goat core — control plane for autonomous agent companies.

Inspired by paperclipai/paperclip's architecture but adapted to goat's
Python/FastAPI stack and JSON-file persistence model.

Layers:
    models         — dataclass entities (Company, Goal, Ticket, Budget, ActivityEntry)
    store          — company-scoped JSON persistence
    activity_log   — append-only audit trail
    cost_tracker   — API cost attribution per ticket
    agent_runtime  — wraps agent execution with ticket lifecycle
"""
