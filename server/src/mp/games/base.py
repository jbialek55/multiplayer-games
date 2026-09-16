"""Stable pluggable game interface.

This is the single seam between the platform and any game. A game implements
``Game`` (static descriptor + session factory) and a ``GameSession`` (one
running game). Platform code depends only on this module; a game never imports
transport, and the platform never touches game internals beyond this contract.

Dependency direction (preserved):
    transport -> domain -> games.base   (games import neither domain nor transport)
"""

from __future__ import annotations

from typing import Sequence, Any


class GameError(Exception):
    """A game-level, user-facing failure (illegal move, not your turn, ...).

    The platform catches this and reports it as an ``error`` delivery to the
    acting player; the game session stays valid.
    """


class GameEvent:
    """A semantic event a game emits from a state transition.

    The platform translates events into wire messages; a game never sends
    messages itself. Standard types:
        STATE  -> the platform sends a ``state_update`` with the full snapshot
        OVER   -> the platform sends a ``game_over`` with state + result
    """

    STATE = "state"
    OVER = "over"

    __slots__ = ("type", "payload")

    def __init__(self, type: str, payload: dict[str, Any] | None = None) -> None:
        self.type = type
        self.payload = payload or {}


class Game:
    """Static descriptor for a game. One instance per game, registered once."""

    def __init__(self, id: str, name: str, min_players: int = 2, max_players: int = 2) -> None:
        self.id = id
        self.name = name
        self.min_players = min_players
        self.max_players = max_players

    def create_session(self, player_ids: Sequence[str]) -> "GameSession":
        raise NotImplementedError("games must implement create_session()")


class GameSession:
    """One running game. Owns all mutable game state for its lifetime.

    Lifecycle: constructed -> ``start()`` -> receive ``handle_input()`` ->
    ``is_finished()`` -> ``result()``. Defaults assume a turn-based, event
    driven game with no background tick; a tick-driven game may override
    ``start``/add its own loop.
    """

    def __init__(self, game_id: str, player_ids: Sequence[str]) -> None:
        self.game_id = game_id
        self.player_ids = list(player_ids)
        self.started: bool = False
        self.finished: bool = False
        # Realtime games set this to the seconds-between-ticks; the platform
        # then runs a background loop calling ``tick()`` and broadcasting the
        # returned events. ``None`` = turn-based (no background loop).
        self.rate: float | None = None

    # --- lifecycle --------------------------------------------------- #
    def start(self) -> list[GameEvent]:
        """Begin the game; return any initial events (e.g. a first snapshot)."""
        self.started = True
        return []

    def is_finished(self) -> bool:
        return self.finished

    def mark_finished(self) -> None:
        """Force the game into a finished state (external cancellation, forfeit).

        Forfeit policy is a platform/network concern, so the platform calls this
        rather than the game deciding it. Games that care may override to also
        update their internal state.
        """
        self.finished = True

    # --- gameplay ---------------------------------------------------- #
    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        """Validate ``action`` and advance state; return resulting events."""
        raise NotImplementedError("games must implement handle_input()")

    def tick(self) -> list[GameEvent]:
        """Advance realtime state once (called by the platform if ``rate`` is
        set). Turn-based games ignore this."""
        return []

    def remove_player(self, player_id: str) -> list[GameEvent]:
        """A player left mid-game (multi-player games). Default: no-op."""
        return []

    def snapshot(self) -> dict[str, Any]:
        """A full, serializable snapshot of the game state."""
        raise NotImplementedError("games must implement snapshot()")

    def result(self) -> dict[str, Any]:
        """The outcome when finished (winner, draw, etc.)."""
        raise NotImplementedError("games must implement result()")

    # --- player lifecycle (defaults: no disconnect handling) --------- #
    def on_player_disconnect(self, player_id: str) -> list[GameEvent]:
        return []

    def on_player_reconnect(self, player_id: str) -> list[GameEvent]:
        return []
