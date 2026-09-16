"""Pure Tic-Tac-Toe rules.

This module contains no I/O, no time, no networking -- only deterministic
state transitions. It is the most tested part of the system and is what makes
the game replayable in tests (see the game-server skill).
"""

from __future__ import annotations

from dataclasses import dataclass, field

X = "X"
O = "O"
SYMBOLS = (X, O)

_WIN_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


class TicTacToeError(ValueError):
    """Raised for any illegal move."""


@dataclass(frozen=True)
class State:
    """Immutable board state; moves produce a new ``State``."""

    board: tuple[str | None, ...] = field(default_factory=lambda: (None,) * 9)
    turn: str = X
    winner: str | None = None
    draw: bool = False

    @property
    def is_finished(self) -> bool:
        return self.winner is not None or self.draw


def new_state() -> State:
    return State()


def _winner_line(board: tuple[str | None, ...]) -> tuple[int, int, int] | None:
    for a, b, c in _WIN_LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return (a, b, c)
    return None


def apply_move(state: State, symbol: str, cell: int) -> State:
    """Return the state after ``symbol`` plays in ``cell``.

    Validates the move (in range, empty cell, correct turn, not finished) and
    raises ``TicTacToeError`` otherwise. Does not mutate ``state``.
    """
    if state.is_finished:
        raise TicTacToeError("game is over")
    if symbol not in SYMBOLS:
        raise TicTacToeError(f"invalid symbol: {symbol}")
    if symbol != state.turn:
        raise TicTacToeError("not that player's turn")
    if not isinstance(cell, int) or not (0 <= cell <= 8):
        raise TicTacToeError(f"cell out of range: {cell}")
    if state.board[cell] is not None:
        raise TicTacToeError(f"cell already taken: {cell}")

    board = list(state.board)
    board[cell] = symbol
    board_t = tuple(board)

    line = _winner_line(board_t)
    if line is not None:
        return State(board=board_t, turn=state.turn, winner=symbol)

    # Draw when the board is full with no winner.
    if all(cell_symbol is not None for cell_symbol in board_t):
        return State(board=board_t, turn=state.turn, draw=True)

    next_turn = O if symbol == X else X
    return State(board=board_t, turn=next_turn)


def winning_line(state: State) -> tuple[int, int, int] | None:
    return _winner_line(state.board)
