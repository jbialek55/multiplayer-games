"""Pong game session (realtime, 2 players). The platform ticks this at
``rate`` seconds and broadcasts the resulting snapshot to both players.
Players report a held paddle direction; the engine moves paddles and the ball.

Phases: ``starting`` (3 s countdown, everything frozen) -> ``running`` ->
back to ``starting`` after every point -> ``finished``.

Paddle input is either a held direction (``{"dir": -1|0|1}``, keyboard) or a
position to move to (``{"target": y}``, a finger dragging the paddle). The
paddle moves at its normal speed either way, so a finger can't teleport it.
"""

from __future__ import annotations

import math
from typing import Any, Sequence
import random

from mp.games.base import CountdownSession, Game, GameEvent, GameError
from mp.games.pong import game as rules


class PongGame(Game):
    def __init__(self) -> None:
        super().__init__(id="pong", name="Pong", min_players=2, max_players=2)

    def create_session(self, player_ids: Sequence[str]) -> "PongSession":
        return PongSession(player_ids)


class PongSession(CountdownSession):
    TICKS_PER_SEC = 60  # 60 ticks/sec for smooth motion
    COUNTDOWN_TICKS = 3 * TICKS_PER_SEC

    def __init__(self, player_ids: Sequence[str]) -> None:
        super().__init__(game_id="pong", player_ids=player_ids)
        if len(player_ids) != 2:
            raise GameError("pong requires exactly 2 players")
        # player_ids[0] = left paddle, player_ids[1] = right paddle.
        self.choice = random.choice([0,1])
        self.sides: dict[str, str] = {player_ids[self.choice]: rules.LEFT, player_ids[1-self.choice]: rules.RIGHT}
        self.state: rules.State = rules.new_state()
        self.inputs: dict[str, int] = {player_ids[0]: 0, player_ids[1]: 0}
        self.targets: dict[str, float | None] = {player_ids[0]: None, player_ids[1]: None}

    # --- lifecycle --------------------------------------------------- #
    def start(self) -> list[GameEvent]:
        self.started = True
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    # --- gameplay ---------------------------------------------------- #
    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        if not self.started:
            raise GameError("game not started")
        if self.is_finished() or self.state.winner is not None:
            raise GameError("game is over")
        if player_id not in self.sides:
            raise GameError("not a participant")
        # Accepted during the countdown too: a player already holding a key (or
        # a finger) starts moving the moment the game begins.
        if "target" in action:
            target = action["target"]
            if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target):
                raise GameError("target must be a number")
            low, high = rules.PAD_H / 2, rules.H - rules.PAD_H / 2
            self.targets[player_id] = max(low, min(high, float(target)))
        else:
            direction = action.get("dir", 0)
            if direction not in (-1, 0, 1):
                raise GameError("dir must be -1, 0, or 1")
            self.inputs[player_id] = int(direction)
            self.targets[player_id] = None  # the keyboard takes over from a finger
        return []  # inputs apply on the next tick

    def tick(self) -> list[GameEvent]:
        """Advance one tick. Called by the platform at ``rate``."""
        if self.is_finished() or self.state.winner is not None:
            return []
        if self.phase == "starting":
            return self.tick_countdown()

        left, right = self.player_ids[self.choice],self.player_ids[1-self.choice]
        before = self.state
        self.state = rules.step(
            self.state,
            dir_l=self._direction(left, before.pad_l),
            dir_r=self._direction(right, before.pad_r),
            dt=self.rate,
        )
        scored = (self.state.score_l, self.state.score_r) != (before.score_l, before.score_r)
        if self.state.winner is not None:
            self.phase = "finished"
            self.finished = True
        elif scored:
            self.begin_countdown()  # the ball is back in the centre: count down to the serve
        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if self.finished:
            events.append(
                GameEvent(
                    GameEvent.OVER,
                    {"state": self.snapshot(), "result": self.result()},
                )
            )
        return events

    def _direction(self, player_id: str, paddle_y: float) -> int:
        """Held direction, or the direction that carries the paddle to the finger."""
        target = self.targets[player_id]
        if target is None:
            return self.inputs[player_id]
        gap = target - paddle_y
        if abs(gap) <= rules.PAD_SPEED * self.rate:  # within one step: arrived
            return 0
        return 1 if gap > 0 else -1

    # --- state ------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "countdown": self.countdown_seconds,
            "ball": {"x": self.state.ball_x, "y": self.state.ball_y},
            "paddles": {"l": self.state.pad_l, "r": self.state.pad_r},
            "scores": {"l": self.state.score_l, "r": self.state.score_r},
            "field": {
                "w": rules.W,
                "h": rules.H,
                "ball_r": rules.BALL_R,
                "pad_h": rules.PAD_H,
                "pad_w": rules.PAD_W,
            },
            "symbols": dict(self.sides),  # player_id -> "L"/"R"
            "finished": self.is_finished(),
            "winner": self._pid_for(self.state.winner),
            "win_score": rules.WIN_SCORE,
        }

    def result(self) -> dict[str, Any]:
        return {
            "winner": self._pid_for(self.state.winner),
            "draw": False,
            "reason": "first_to_win_score",
        }

    def _pid_for(self, side: str | None) -> str | None:
        for pid, s in self.sides.items():
            if s == side:
                return pid
        return None
