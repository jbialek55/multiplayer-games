"""Pong game plugin."""

from __future__ import annotations

from mp.games.pong.game import State, new_state, step
from mp.games.pong.session import PongGame, PongSession

PONG = PongGame()

__all__ = ["PONG", "PongGame", "PongSession", "State", "new_state", "step"]
