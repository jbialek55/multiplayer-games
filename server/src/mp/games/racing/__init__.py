"""Simple Racing game plugin."""

from __future__ import annotations

from mp.games.racing.game import Car, State, start_cars, step
from mp.games.racing.session import RacingGame, RacingSession

RACING = RacingGame()

__all__ = ["RACING", "RacingGame", "RacingSession", "Car", "State", "start_cars", "step"]
