"""API cost attribution.

Wrap agent execution with `track()` → any inner code calling `record(kind, units)`
attributes spend to that context. After the block, pull `total_usd()` and
`breakdown()` onto the ticket.

Prices are estimates; user can override via CostContext(prices=...).

    with track() as ctx:
        record("apify.place", units=100)
        record("claude.token_in", units=2500)
    ticket["cost_usd"] = ctx.total_usd()
    ticket["cost_breakdown"] = ctx.breakdown()

No active context → record() is a no-op. Safe to instrument any hot path.
"""

import contextvars
from contextlib import contextmanager
from typing import Optional


# Rough USD-per-unit estimates. Users with real invoices can tune via
# companies/{id}/cost_prices.json (future phase).
DEFAULT_PRICES = {
    # Apify (estimates; real cost depends on compute units)
    "apify.run": 0.003,                  # per Apify compute unit, approx
    "apify.gmaps.place": 0.002,          # compass extractor estimate
    "apify.gmaps.lukaskrivka": 0.0021,   # memory-confirmed
    "apify.contact_scraper.page": 0.00105,

    # fal.ai
    "fal.image.sdxl": 0.025,
    "fal.image.flux": 0.05,

    # ElevenLabs
    "elevenlabs.char": 0.00015,

    # Claude (Opus 4.x — conservative, update with your actual tier)
    "claude.token_in": 0.000015,
    "claude.token_out": 0.000075,

    # Kie.ai
    "kie.video.6s": 0.08,

    # Email finder providers (per valid email)
    "emailapi.email": 0.025,
    "leadmagic.email": 0.007,
    "generect.email": 0.04,
    "apify_web.email": 0.002,

    # YouTube Data API — free, but track quota usage
    "youtube.upload": 0.0,

    # Instantly.ai — subscription, not metered
    "instantly.campaign": 0.0,
    "instantly.lead": 0.0,
}


class CostContext:
    """Collects cost events for one ticket's lifetime."""

    def __init__(self, prices: Optional[dict] = None):
        self.prices = dict(DEFAULT_PRICES)
        if prices:
            self.prices.update(prices)
        self.events: list = []  # [{kind, units, usd, meta}]

    def add(self, kind: str, units: float = 1.0, meta: Optional[dict] = None) -> float:
        price_per_unit = self.prices.get(kind, 0.0)
        usd = round(units * price_per_unit, 6)
        self.events.append({
            "kind": kind,
            "units": units,
            "usd": usd,
            "meta": meta or {},
        })
        return usd

    def total_usd(self) -> float:
        return round(sum(e["usd"] for e in self.events), 4)

    def breakdown(self) -> dict:
        """Sum USD by event kind."""
        out: dict = {}
        for e in self.events:
            out[e["kind"]] = round(out.get(e["kind"], 0.0) + e["usd"], 4)
        return out


# ContextVar so nested calls in async/thread all attribute to the same ticket.
_active: contextvars.ContextVar[Optional[CostContext]] = contextvars.ContextVar(
    "goat_cost_ctx", default=None
)


@contextmanager
def track(ctx: Optional[CostContext] = None, prices: Optional[dict] = None):
    """Activate a CostContext for the duration of the block."""
    ctx = ctx or CostContext(prices=prices)
    token = _active.set(ctx)
    try:
        yield ctx
    finally:
        _active.reset(token)


def record(kind: str, units: float = 1.0, meta: Optional[dict] = None) -> float:
    """Record a cost event against the active context. No-op if none active."""
    ctx = _active.get()
    if ctx is None:
        return 0.0
    return ctx.add(kind, units, meta)


def current() -> Optional[CostContext]:
    """Return the currently-active context, if any."""
    return _active.get()
