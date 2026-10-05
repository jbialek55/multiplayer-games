"""Snake Battle session (realtime, 2..4 players).

The platform ticks this at ``rate`` seconds. Direction inputs are queued (a
few per player, so a quick "up, then left" swipe is not collapsed into just
"left") and one turn is consumed per tick; all snakes move simultaneously.
Phases:

    starting  -> countdown ticks (snakes frozen)
    running   -> snakes move, food spawns, collisions resolve
    finished  -> one survivor (or a deterministic tie-break) wins
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import Any, Sequence

from mp.games.base import CountdownSession, Game, GameEvent, GameError
from mp.games.snake import game as rules


class SnakeGame(Game):
    def __init__(self) -> None:
        super().__init__(id="snake", name="Snake Battle", min_players=2, max_players=4)

    def create_session(self, player_ids: Sequence[str]) -> "SnakeSession":
        return SnakeSession(player_ids)


class SnakeSession(CountdownSession):
    TICKS_PER_SEC = 8
    COUNTDOWN_TICKS = 3 * TICKS_PER_SEC
    MAX_QUEUED_TURNS = 3

    def __init__(self, player_ids: Sequence[str]) -> None:
        super().__init__(game_id="snake", player_ids=player_ids)
        if not (2 <= len(player_ids) <= 4):
            raise GameError("snake requires between 2 and 4 players")
        self.turns: dict[str, deque[tuple[int, int]]] = {
            pid: deque(maxlen=self.MAX_QUEUED_TURNS) for pid in player_ids
        }
        snakes = rules.start_positions(list(player_ids))
        self.state = rules.State(snakes=snakes, food=rules.spawn_initial_food(snakes))

    # --- lifecycle --------------------------------------------------- #
    def start(self) -> list[GameEvent]:
        self.started = True
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    # --- gameplay ---------------------------------------------------- #
    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        if not self.started:
            raise GameError("game not started")
        if self.phase == "finished" or self.state.winner is not None:
            raise GameError("game is over")
        d = action.get("dir")
        if d not in rules.DIRS:
            raise GameError("dir must be up, down, left, or right")
        turns = self.turns.get(player_id)
        if turns is None:
            raise GameError("not a participant")
        turns.append(rules.DIRS[d])
        return []  # applied on a following tick

    def tick(self) -> list[GameEvent]:
        if self.phase == "finished":
            return []
        if self.phase == "starting":
            return self.tick_countdown()

        # RUNNING: apply each snake's next queued turn, then advance the simulation
        snakes = []
        for s in self.state.snakes:
            d = self._next_turn(s)
            snakes.append(replace(s, next_dir=d) if d is not None else s)
        self.state = rules.step(
            rules.State(snakes=tuple(snakes), food=self.state.food, tick=self.state.tick)
        )

        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if self.state.final_round:
            events.append(self._finish())
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
            self.state = replace(self.state, winner=alive[0].player_id, final_round=True)
            events.append(self._finish())
        elif len(alive) == 0:
            self.state = replace(self.state, winner=rules.tiebreak(snakes), final_round=True)
            events.append(self._finish())
        return events

    def _next_turn(self, snake: rules.Snake) -> tuple[int, int] | None:
        """Oldest queued direction that is a real turn (not straight on, not a reversal)."""
        turns = self.turns.get(snake.player_id)
        while turns:
            d = turns.popleft()
            if d not in (snake.dir, rules.OPPOSITE[snake.dir]):
                return d
        return None

    def _finish(self) -> GameEvent:
        self.phase = "finished"
        self.finished = True
        return GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()})

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
            "countdown": self.countdown_seconds,
            "board": {"w": rules.W, "h": rules.H},
            "snakes": snakes_out,
            "food": [[x, y] for x, y in self.state.food],
            "winner": self.state.winner,
            "finished": self.phase == "finished",
            "symbols": {s.player_id: s.color for s in self.state.snakes},
        }

    def result(self) -> dict[str, Any]:
        return {"winner": self.state.winner, "draw": False, "reason": "survival"}
