"""Server-side mutable state.

Single ``ServerState`` instance per process, created at startup and attached to
the FastAPI app. Ownership rule: this module owns *cross-cutting* references
(players, rooms, matchmaking queues, active game sessions, the game registry).
Each ``GameSession`` owns only its own game state and is never mutated here.

Concurrency: everything mutates inside one asyncio event loop, and we never
``await`` between reading state and committing the mutation, so no locks are
needed. That is a deliberate invariant, not an accident
"""

from __future__ import annotations

import secrets
from collections import deque
from dataclasses import dataclass, field

from mp.domain.players import Player
from mp.domain.rooms import Room
from mp.games.base import GameSession
from mp.games.registry import GameRegistry
from mp.protocol.messages import RoomInfo


def new_public_id() -> str:
    """Collision-resistant public id with a short, human-usable form."""
    return secrets.token_hex(4)


@dataclass
class ServerState:
    """All in-memory cross-cutting state."""

    players: dict[str, Player] = field(default_factory=dict)
    rooms: dict[str, Room] = field(default_factory=dict)
    queues: dict[str, deque[str]] = field(default_factory=dict)  # game_id -> player ids
    sessions: dict[str, GameSession] = field(default_factory=dict)
    registry: GameRegistry = field(default_factory=GameRegistry)

    # --- players --- #
    def new_player(self, addr: str) -> Player:
        player = Player(id=new_public_id(), addr=addr)
        self.players[player.id] = player
        return player

    # --- rooms --- #
    def create_room(self, host_id: str, game_id: str) -> Room:
        room = Room(id=new_public_id(), game_id=game_id, host_id=host_id)
        self.rooms[room.id] = room
        room.players.setdefault(host_id)
        return room

    def live_rooms(self) -> list[RoomInfo]:
        return [room.info() for room in self.rooms.values() if room.is_open()]

    # --- matchmaking queue --- #
    def enqueue(self, game_id: str, player_id: str) -> None:
        self.queues.setdefault(game_id, deque()).append(player_id)

    def pop_opponent(self, game_id: str) -> str | None:
        """Pop and return the first queued player in ``game_id``, if any."""
        q = self.queues.get(game_id)
        if q:
            return q.popleft()
        return None

    def is_queued(self, player_id: str) -> str | None:
        """Return the game_id the player is queued in, or None."""
        for game_id, q in self.queues.items():
            if player_id in q:
                return game_id
        return None

    def dequeue_player(self, player_id: str) -> None:
        """Remove ``player_id`` from every queue (used on disconnect)."""
        for q in self.queues.values():
            while player_id in q:
                q.remove(player_id)
