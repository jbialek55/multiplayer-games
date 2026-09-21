"""Anonymous player identity.

A player has no credentials for the MVP: the server issues a UUID on connect
and owns the identity for the life of the connection. Clients never supply
their own id
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Player:
    id: str
    addr: str
    current_room_id: str | None = None
    connected: bool = True
