"""Pluggable games package.

``build_default_registry`` registers every bundled game. Adding a game means
adding a package implementing ``mp.games.base.Game`` and listing it here --
nothing in transport or platform code changes.
"""

from __future__ import annotations

from mp.games.registry import GameRegistry
from mp.games.tictactoe import TIC_TAC_TOE
from mp.games.chess import CHESS
from mp.games.quiz import QUIZ
from mp.games.pong import PONG
from mp.games.snake import SNAKE
from mp.games.racing import RACING


def build_default_registry() -> GameRegistry:
    registry = GameRegistry()
    registry.register(TIC_TAC_TOE)
    registry.register(CHESS)
    registry.register(QUIZ)
    registry.register(PONG)
    registry.register(SNAKE)
    registry.register(RACING)
    return registry
