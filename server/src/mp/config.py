"""Runtime configuration for the multiplayer server.
    host, port, limit, strikes, max_rooms, db are read from env variables

"""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable server settings.

    A single frozen instance is created at startup and cached on the app; code
    reads from it rather than constructing its own copies.
    """

    host: str = "127.0.0.1"
    port: int = 8000

    # Transport limits (defense against hostile/broken clients).
    max_message_bytes: int = 65_536          # 64 KiB
    max_dispatch_strikes: int = 3            # protocol violations before close
    rate_limit_capacity: int = 40            # token bucket capacity
    rate_limit_refill_per_sec: float = 20.0  # token refill rate
    rate_limit_cost: int = 1                 # tokens per state-changing msg

    # Room limits (basic server sanity bound).
    max_rooms: int = 128

    # Reconnect grace window (seconds) before a mid-game disconnect forfeits.
    # 0 => forfeit immediately; >0 => the opponent is told the player may return.
    reconnect_grace_seconds: float = 10.0

    # How often (seconds) the server frees players who never came back, and
    # the rooms/sessions only they were keeping alive.
    sweep_interval_seconds: float = 30.0

    # SQLite path for completed-game history. None disables persistence
    # (used by tests); the production default is a local ``mp.db`` file.
    db_path: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings, honouring a small set of env overrides."""
        return cls(
            host=os.environ.get("MP_HOST", "127.0.0.1"),
            port=_env_int("MP_PORT", 8000),
            max_message_bytes=_env_int("MP_MAX_MSG_BYTES", 65_536),
            max_dispatch_strikes=_env_int("MP_MAX_STRIKES", 3),
            max_rooms=_env_int("MP_MAX_ROOMS", 128),
            db_path=os.environ.get("MP_DB") or "mp.db",
        )


DEFAULTS: Settings = Settings.from_env()
