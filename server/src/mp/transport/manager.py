"""Connection registry: maps a player id to their connected ``Client``.

Used by the endpoint to fan a ``Delivery`` out to the right socket. Because
this is transport state, it lives here and never leaks into platform/game
code.
"""

from __future__ import annotations

from mp.transport.connection import Client


class ConnectionRegistry:
    def __init__(self) -> None:
        self._by_player: dict[str, Client] = {}

    def bind(self, client: Client) -> None:
        if client.player_id is not None:
            self._by_player[client.player_id] = client

    def unbind(self, client: Client) -> None:
        if client.player_id is not None:
            self._by_player.pop(client.player_id, None)

    def get(self, player_id: str) -> Client | None:
        return self._by_player.get(player_id)
