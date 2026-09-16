"""Room management.

A room is the *social* container: it decides who plays together and is a
separate concept from a ``GameSession`` (which decides what happens during the
game). For the MVP a room has explicit lifecycle states:

    waiting -> (full / host starts) -> closed
    waiting -> (everyone leaves)     -> closed
    playing -> (game finished)       -> closed

The game itself lives inside a session (later milestones); rooms only reference
the game type and hold the player roster.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mp.protocol.messages import RoomInfo


class RoomStatus:
    WAITING = "waiting"
    PLAYING = "playing"
    CLOSED = "closed"


@dataclass
class Room:
    id: str
    game_id: str
    host_id: str
    status: str = RoomStatus.WAITING
    players: dict[str, None] = field(default_factory=dict)  # ordered roster
    session_id: str | None = None
    rematch_votes: set[str] = field(default_factory=set)

    def is_open(self) -> bool:
        return self.status == RoomStatus.WAITING

    def start(self, session_id: str) -> None:
        """Transition a full room into a running game session."""
        self.status = RoomStatus.PLAYING
        self.session_id = session_id

    def add_player(self, player_id: str) -> None:
        if player_id not in self.players:
            self.players[player_id] = None

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        if not self.players:
            self.status = RoomStatus.CLOSED
        elif self.host_id == player_id and self.players:
            # Promote the next joined player to host so the room stays usable.
            self.host_id = next(iter(self.players))

    def info(self) -> RoomInfo:
        return RoomInfo(
            id=self.id,
            game_id=self.game_id,
            host_id=self.host_id,
            players=list(self.players),
            status=self.status,
        )
