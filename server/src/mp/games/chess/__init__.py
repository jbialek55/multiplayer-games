"""Chess game plugin."""

from __future__ import annotations

from mp.games.chess.game import Move, State, apply_move, initial_state, legal_moves, parse_sq, sq_name
from mp.games.chess.session import ChessGame, ChessSession

CHESS = ChessGame()

__all__ = [
    "CHESS",
    "ChessGame",
    "ChessSession",
    "Move",
    "State",
    "apply_move",
    "initial_state",
    "legal_moves",
    "parse_sq",
    "sq_name",
]
