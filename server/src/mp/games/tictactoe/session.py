"""Tic-Tac-Toe game plugin.

Implements the ``Game`` / ``GameSession`` contract over the pure rules in
``game.py``. Holds all mutable game state, validates every move (right turn,
empty/in-range cell, not finished), and emits semantic ``GameEvent``\\ s for the
platform to broadcast. No networking or platform imports here.
"""

from __future__ import annotations

from typing import Any, Sequence
import random
from mp.games.base import Game, GameEvent, GameError, GameSession
from mp.games.tictactoe.game import (
    O,
    X,
    State,
    TicTacToeError,
    apply_move,
    new_state,
    winning_line,
)
# import logging
# log = logging.getLogger("session")
class TicTacToeGame(Game):
    def __init__(self) -> None:
        super().__init__(id="tictactoe", name="Tic-Tac-Toe", min_players=2, max_players=2)

    def create_session(self, player_ids: Sequence[str]) -> "TicTacToeSession":
        return TicTacToeSession(player_ids)


class TicTacToeSession(GameSession):
    def __init__(self, player_ids: Sequence[str]) -> None:
        super().__init__(game_id="tictactoe", player_ids=player_ids)
        if len(player_ids) != 2:
            raise GameError("tictactoe requires exactly 2 players")
        # First player is X, second is O.
        guess = random.randint(0,1)
        self.symbols: dict[str, str] = {player_ids[guess]: X, player_ids[1-guess]: O}
        self.state: State = new_state()

    # --- lifecycle --------------------------------------------------- #
    def start(self) -> list[GameEvent]:
        self.started = True
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    # --- gameplay ---------------------------------------------------- #
    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        #log.info("WCHODZI: gracz=%s cell=%s", player_id, action.get("cell"))
        if not self.started:
            raise GameError("game not started")
        if self.is_finished() or self.state.is_finished:
            raise GameError("game is over")
        symbol = self.symbols.get(player_id)
        if symbol is None:
            raise GameError("not a participant")

        cell = action.get("cell")
        try:
            self.state = apply_move(self.state, symbol, cell)
        except TicTacToeError as exc:
            raise GameError(str(exc)) from exc

        events: list[GameEvent] = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if self.state.is_finished:
            self.finished = True
            events.append(
                GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()})
            )
        return events

    # --- state ------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        return {
            "board": list(self.state.board),
            "turn": self.state.turn,
            "whos_turn": self._player_for_symbol(self.state.turn),
            "winner": self.state.winner,
            "draw": self.state.draw,
            "finished": self.state.is_finished,
            "symbols": dict(self.symbols),
        }

    def result(self) -> dict[str, Any]:
        line = winning_line(self.state)
        return {
            "winner": self.state.winner,
            "draw": self.state.draw,
            "winning_line": list(line) if line is not None else None,
        }

    # --- helpers ----------------------------------------------------- #
    def role_of(self, player_id: str) -> str | None:
        return self.symbols.get(player_id)

    def _player_for_symbol(self, symbol: str) -> str | None:
        for pid, sym in self.symbols.items():
            if sym == symbol:
                return pid
        return None
