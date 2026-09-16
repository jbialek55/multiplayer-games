"""Snake Battle session (realtime, 2..4 players).

The platform ticks this at ``rate`` seconds. Direction inputs are buffered and
applied on the next tick; all snakes move simultaneously. Phases:

    starting  -> countdown ticks (snakes frozen)
    running   -> snakes move, food spawns, collisions resolve
    finished  -> one survivor (or a deterministic tie-break) wins
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Sequence

from mp.games.base import Game, GameEvent, GameError, GameSession
from mp.games.snake import game as rules


class SnakeGame(Game):
    def __init__(self) -> None:
        super().__init__(id="snake", name="Snake Battle", min_players=2, max_players=4)

    def create_session(self, player_ids: Sequence[str]) -> "SnakeSession":
        return SnakeSession(player_ids)


class SnakeSession(GameSession):
    TICKS_PER_SEC = 8
    COUNTDOWN_TICKS = 24  # ~3 second countdown

    def __init__(self, player_ids: Sequence[str]) -> None:
        super().__init__(game_id="snake", player_ids=player_ids)
        if not (2 <= len(player_ids) <= 4):
            raise GameError("snake requires between 2 and 4 players")
        self.rate = 1 / self.TICKS_PER_SEC
        self.phase = "starting"
        self.countdown = self.COUNTDOWN_TICKS
        self.buffered: dict[str, tuple[int, int]] = {}
        self.state = rules.State(snakes=rules.start_positions(list(player_ids)), food=rules.spawn_initial_food(rules.start_positions(list(player_ids))))
        self.round_over = False

    # --- lifecycle --------------------------------------------------- #
    def start(self) -> list[GameEvent]:
        self.started = True
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    # --- gameplay ---------------------------------------------------- #
    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        if not self.started:
            raise GameError("game not started")
        if self.phase == "finished" or self.round_over:
            raise GameError("game is over")
        d = action.get("dir")
        if d not in rules.DIRS:
            raise GameError("dir must be up, down, left, or right")
        self.buffered[player_id] = rules.DIRS[d]
        return []  # applied on the next tick

    def tick(self) -> list[GameEvent]:
        if self.phase == "finished":
            return []
        if self.phase == "starting":
            self.countdown -= 1
            if self.countdown <= 0:
                self.phase = "running"
            return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

        # RUNNING: apply buffered directions, then advance the simulation
        snakes = []
        for s in self.state.snakes:
            d = self.buffered.get(s.player_id)
            snakes.append(replace(s, next_dir=d) if d is not None else s)
        self.state = rules.step(
            rules.State(snakes=tuple(snakes), food=self.state.food, tick=self.state.tick)
        )

        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if self.state.final_round:
            self.phase = "finished"
            self.round_over = True
            self.finished = True
            events.append(
                GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()})
            )
        return events

    def remove_player(self, player_id: str) -> list[GameEvent]:
        if player_id not in self.player_ids or self.phase == "finished":
            return []
        snakes = tuple(
            replace(s, alive=False) if s.player_id == player_id else s for s in self.state.snakes
        )
        self.player_ids.remove(player_id)
        self.state = rules.State(snakes=snakes, food=self.state.food, tick=self.state.tick)

        alive = [s for s in snakes if s.alive]
        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if len(alive) == 1:
            self.phase = "finished"
            self.round_over = True
            self.finished = True
            self.state = replace(self.state, winner=alive[0].player_id, final_round=True)
            events.append(
                GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()})
            )
        elif len(alive) == 0:
            self.phase = "finished"
            self.round_over = True
            self.finished = True
            self.state = replace(self.state, winner=rules.tiebreak(snakes), final_round=True)
            events.append(
                GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()})
            )
        return events

    # --- state ------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        snakes_out = []
        for s in self.state.snakes:
            snakes_out.append(
                {
                    "player_id": s.player_id,
                    "color": s.color,
                    "alive": s.alive,
                    "score": s.score,
                    "dir": [s.dir[0], s.dir[1]],
                    "body": [[x, y] for x, y in s.body],
                }
            )
        return {
            "phase": self.phase,
            "countdown": max(0, math.ceil(self.countdown / self.TICKS_PER_SEC)),
            "board": {"w": rules.W, "h": rules.H},
            "snakes": snakes_out,
            "food": [[x, y] for x, y in self.state.food],
            "winner": self.state.winner,
            "finished": self.phase == "finished",
            "round_over": self.round_over,
            "symbols": {s.player_id: s.color for s in self.state.snakes},
            "color_palette": rules.PALETTE,
        }

    def result(self) -> dict[str, Any]:
        return {"winner": self.state.winner, "draw": False, "reason": "survival"}
