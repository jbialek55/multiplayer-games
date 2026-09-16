"""Pong game session (realtime, 2 players). The platform ticks this at
``rate`` seconds and broadcasts the resulting snapshot to both players.
Players report a held paddle direction; the engine moves paddles and the ball.
"""

from __future__ import annotations

from typing import Any, Sequence

from mp.games.base import Game, GameEvent, GameError, GameSession
from mp.games.pong import game as rules


class PongGame(Game):
    def __init__(self) -> None:
        super().__init__(id="pong", name="Pong", min_players=2, max_players=2)

    def create_session(self, player_ids: Sequence[str]) -> "PongSession":
        return PongSession(player_ids)


class PongSession(GameSession):
    def __init__(self, player_ids: Sequence[str]) -> None:
        super().__init__(game_id="pong", player_ids=player_ids)
        if len(player_ids) != 2:
            raise GameError("pong requires exactly 2 players")
        # player_ids[0] = left paddle, player_ids[1] = right paddle.
        self.sides: dict[str, str] = {player_ids[0]: rules.LEFT, player_ids[1]: rules.RIGHT}
        self.state: rules.State = rules.new_state()
        self.inputs: dict[str, int] = {player_ids[0]: 0, player_ids[1]: 0}
        self.rate = 1 / 60  # 60 ticks/sec for smooth motion

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
        side = self.sides.get(player_id)
        if side is None:
            raise GameError("not a participant")
        direction = action.get("dir", 0)
        if direction not in (-1, 0, 1):
            raise GameError("dir must be -1, 0, or 1")
        self.inputs[player_id] = int(direction)
        return []  # inputs apply on the next tick

    def tick(self) -> list[GameEvent]:
        """Advance one tick. Called by the platform at ``rate``."""
        if self.is_finished() or self.state.winner is not None:
            return []
        self.state = rules.step(
            self.state,
            dir_l=self.inputs[self.player_ids[0]],
            dir_r=self.inputs[self.player_ids[1]],
            dt=self.rate,
        )
        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if self.state.winner is not None:
            self.finished = True
            events.append(
                GameEvent(
                    GameEvent.OVER,
                    {"state": self.snapshot(), "result": self.result()},
                )
            )
        return events

    # --- state ------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        winner_pid = None
        if self.state.winner is not None:
            winner_pid = self._pid_for(self.state.winner)
        return {
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
            "winner": winner_pid,
            "win_score": rules.WIN_SCORE,
        }

    def result(self) -> dict[str, Any]:
        return {
            "winner": self._pid_for(self.state.winner) if self.state.winner else None,
            "draw": False,
            "reason": "first_to_win_score",
        }

    def _pid_for(self, side: str) -> str | None:
        for pid, s in self.sides.items():
            if s == side:
                return pid
        return None
