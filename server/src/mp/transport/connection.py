"""Per-connection transport state (kept out of game/domain code).

Objects here know how to ``send`` on a WebSocket but never contain game rules.
Routing instructions (``Delivery``) live in ``mp.protocol`` so both transport
and platform can use them without importing each other.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Optional

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


class RateLimiter:
    """Simple in-process token bucket.

    Enough for the MVP: it bounds how fast a single client can issue
    state-changing commands without any external dependency.
    """

    def __init__(self, capacity: float, refill_per_sec: float, cost: float = 1.0) -> None:
        self.capacity = capacity
        self.tokens = capacity
        self.refill_per_sec = refill_per_sec
        self.cost = cost
        self._updated = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._updated
        self._updated = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        if self.tokens >= self.cost:
            self.tokens -= self.cost
            return True
        return False


class Client:
    """One connected WebSocket on the server side.

    Holds the live socket, the player id it is bound to, and per-connection
    transport state (rate limiter, protocol-violation strikes, received seq).
    """

    def __init__(self, connection_id: str, send: SendFn, settings) -> None:
        self.connection_id = connection_id
        self._send = send
        self.player_id: Optional[str] = None  # bound on successful hello
        self.strikes: int = 0
        self.limiter = RateLimiter(
            capacity=settings.rate_limit_capacity,
            refill_per_sec=settings.rate_limit_refill_per_sec,
            cost=settings.rate_limit_cost,
        )

    def take_strike(self) -> int:
        self.strikes += 1
        return self.strikes

    async def send(self, message: dict[str, Any]) -> None:
        """Send an already-encoded message. Errors surface to the caller."""
        await self._send(message)
