"""Chess game plugin: session over the pure engine."""

from __future__ import annotations

from typing import Any, Sequence

from mp.games.base import Game, GameEvent, GameError, GameSession
from mp.games.chess import game as rules


class ChessGame(Game):
    def __init__(self) -> None:
        super().__init__(id="chess", name="Chess", min_players=2, max_players=2)

    def create_session(self, player_ids: Sequence[str]) -> "ChessSession":
        return ChessSession(player_ids)


class ChessSession(GameSession):
    def __init__(self, player_ids: Sequence[str]) -> None:
        super().__init__(game_id="chess", player_ids=player_ids)
        if len(player_ids) != 2:
            raise GameError("chess requires exactly 2 players")
        # player_ids[0] plays white (moves first), player_ids[1] plays black.
        self.colors: dict[str, str] = {
            player_ids[0]: rules.WHITE,
            player_ids[1]: rules.BLACK,
        }
        self._color_to_player = {v: k for k, v in self.colors.items()}
        self.state: rules.State = rules.initial_state()

    # --- lifecycle --------------------------------------------------- #
    def start(self) -> list[GameEvent]:
        self.started = True
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    # --- gameplay ---------------------------------------------------- #
    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        if not self.started:
            raise GameError("game not started")
        if self.state.is_over or self.is_finished():
            raise GameError("game is over")
        color = self.colors.get(player_id)
        if color is None:
            raise GameError("not a participant")
        if color != self.state.turn:
            raise GameError("it is not your move")

        try:
            from_sq = rules.parse_sq(action["from"])
            to_sq = rules.parse_sq(action["to"])
        except (KeyError, TypeError, IndexError) as exc:
            raise GameError("invalid move squares") from exc

        move = self._resolve_move(from_sq, to_sq, action.get("promo"))
        self.state = rules.apply_move(self.state, move)

        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        outcome = rules.result(self.state)
        if outcome.get("winner") is not None or outcome.get("draw"):
            self.finished = True
            events.append(
                GameEvent(
                    GameEvent.OVER,
                    {"state": self.snapshot(), "result": self._result(outcome)},
                )
            )
        return events

    def _resolve_move(self, from_sq: int, to_sq: int, promo: str | None) -> rules.Move:
        candidates = [
            m for m in rules.legal_moves(self.state) if m.from_sq == from_sq and m.to_sq == to_sq
        ]
        if not candidates:
            raise GameError("illegal move")
        if len(candidates) == 1:
            return candidates[0]
        # promotion: pick requested piece or default queen
        wanted = (promo or "q").lower()
        for m in candidates:
            if (m.promo or "q").lower() == wanted:
                return m
        raise GameError("invalid promotion piece")

    # --- state ------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        board_rows: list[list[str | None]] = []
        for r in range(7, -1, -1):  # rank 8 (top) first for visual row-major
            row: list[str | None] = []
            for f in range(8):
                pc = self.state.board[rules._idx(f, r)]
                row.append(pc)
            board_rows.append(row)

        sees = self.state.turn
        whos = self._color_to_player.get(sees)
        outcome = rules.result(self.state)
        over = outcome.get("winner") is not None or outcome.get("draw")

        legal: list[dict[str, Any]] = []
        seen: set[tuple[int, int]] = set()
        for m in rules.legal_moves(self.state):
            key = (m.from_sq, m.to_sq)
            if key in seen:
                continue
            seen.add(key)
            legal.append(
                {
                    "from": rules.sq_name(m.from_sq),
                    "to": rules.sq_name(m.to_sq),
                    "promo": m.promo or "q",
                }
            )

        last = self.state.last
        return {
            "board": board_rows,
            "turn": sees,
            "whos_turn": whos,
            "symbols": dict(self.colors),
            "in_check": rules.in_check(self.state, sees),
            "finished": over,
            "is_over": self.state.is_over,
            "winner": self._winner_pid(outcome),
            "draw": bool(outcome.get("draw")),
            "reason": outcome.get("reason"),
            "legal_moves": legal,
            "last": {"from": rules.sq_name(last.from_sq), "to": rules.sq_name(last.to_sq)}
            if last
            else None,
        }

    def result(self) -> dict[str, Any]:
        outcome = rules.result(self.state)
        return {
            "winner": self._winner_pid(outcome),
            "draw": bool(outcome.get("draw")),
            "reason": outcome.get("reason"),
        }

    def _winner_pid(self, outcome: dict) -> str | None:
        winner_color = outcome.get("winner")
        if winner_color is None:
            return None
        return self._color_to_player.get(winner_color)

    def _result(self, outcome: dict) -> dict[str, Any]:
        return {
            "winner": self._winner_pid(outcome),
            "draw": bool(outcome.get("draw")),
            "reason": outcome.get("reason"),
        }
