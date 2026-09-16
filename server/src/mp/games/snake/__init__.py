"""Snake Battle game plugin."""

from __future__ import annotations

from mp.games.snake.game import (
    PALETTE,
    State,
    start_positions,
    step,
)
from mp.games.snake.session import SnakeGame, SnakeSession

SNAKE = SnakeGame()

__all__ = [
    "SNAKE",
    "SnakeGame",
    "SnakeSession",
    "State",
    "start_positions",
    "step",
    "PALETTE",
]
