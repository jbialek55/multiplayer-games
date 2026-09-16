"""Registry of available games.

Games self-register at startup via ``register()``. Adding a game means adding a
package that implements ``mp.games.base.Game`` and registering it here -- no
changes to transport or platform code.
"""

from __future__ import annotations

from typing import Sequence

from mp.games.base import Game, GameSession


class GameRegistry:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}

    def register(self, game: Game) -> None:
        self._games[game.id] = game

    def get(self, game_id: str) -> Game | None:
        return self._games.get(game_id)

    def create_session(self, game_id: str, player_ids: Sequence[str]) -> GameSession:
        game = self.get(game_id)
        if game is None:
            raise KeyError(f"unknown game: {game_id}")
        return game.create_session(player_ids)

    def all(self) -> list[Game]:
        return list(self._games.values())
