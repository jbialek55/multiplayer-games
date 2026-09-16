"""Simple Racing session (realtime, 2..4 players).

The platform ticks this at ``rate`` seconds. Cars move with simple kinematics
under authoritative control; the race proceeds starting -> racing -> finished.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Sequence

from mp.games.base import Game, GameEvent, GameError, GameSession
from mp.games.racing import game as rules


class RacingGame(Game):
    def __init__(self) -> None:
        super().__init__(id="racing", name="Racing", min_players=2, max_players=4)

    def create_session(self, player_ids: Sequence[str]) -> "RacingSession":
        return RacingSession(player_ids)


class RacingSession(GameSession):
    TICKS_PER_SEC = 24
    COUNTDOWN_TICKS = 72  # ~3 second countdown

    def __init__(self, player_ids: Sequence[str]) -> None:
        super().__init__(game_id="racing", player_ids=player_ids)
        if not (2 <= len(player_ids) <= 4):
            raise GameError("racing requires between 2 and 4 players")
        self.rate = 1 / self.TICKS_PER_SEC
        self.phase = "starting"
        self.countdown = self.COUNTDOWN_TICKS
        self.inputs: dict[str, dict] = {pid: {} for pid in player_ids}
        self.state = rules.State(cars=rules.start_cars(list(player_ids)))

    def start(self) -> list[GameEvent]:
        self.started = True
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        if not self.started:
            raise GameError("game not started")
        if self.phase == "finished":
            raise GameError("game is over")
        self.inputs[player_id] = {
            "accel": bool(action.get("accel")),
            "brake": bool(action.get("brake")),
            "left": bool(action.get("left")),
            "right": bool(action.get("right")),
        }
        return []

    def tick(self) -> list[GameEvent]:
        if self.phase == "finished":
            return []
        if self.phase == "starting":
            self.countdown -= 1
            if self.countdown <= 0:
                self.phase = "racing"
            return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

        self.state = rules.step(self.state, self.inputs, self.rate)
        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if self.state.finished:
            self.phase = "finished"
            self.finished = True
            events.append(
                GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()})
            )
        return events

    def remove_player(self, player_id: str) -> list[GameEvent]:
        if player_id not in self.player_ids or self.phase == "finished":
            return []
        # a leaver simply stops racing; the race continues for the rest
        self.inputs[player_id] = {}
        self.player_ids.remove(player_id)
        cars = tuple(
            replace(c, speed=0.0) if c.player_id == player_id else c for c in self.state.cars
        )
        self.state = replace(self.state, cars=cars)
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    def snapshot(self) -> dict[str, Any]:
        cars = []
        for c in self.state.cars:
            cars.append(
                {
                    "player_id": c.player_id,
                    "color": c.color,
                    "x": c.x,
                    "y": c.y,
                    "heading": c.heading,
                    "speed": c.speed,
                    "lap": c.lap,
                    "finished": c.finished,
                }
            )
        return {
            "phase": self.phase,
            "countdown": max(0, math.ceil(self.countdown / self.TICKS_PER_SEC)),
            "track": {
                "w": rules.W,
                "h": rules.H,
                "island": list(rules.ISLAND),
                "checkpoints": [list(cp) for cp in rules.CHECKPOINTS],
                "required_laps": rules.REQUIRED_LAPS,
            },
            "cars": cars,
            "winner": self.state.winner,
            "order": list(self.state.order),
            "finished": self.phase == "finished",
            "symbols": {c.player_id: c.color for c in self.state.cars},
            "color_palette": list(rules.PALETTE),
        }

    def result(self) -> dict[str, Any]:
        return {"winner": self.state.winner, "order": list(self.state.order), "draw": False, "reason": "completed"}
