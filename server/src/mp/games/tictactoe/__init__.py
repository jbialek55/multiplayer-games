"""Tic-Tac-Toe game plugin."""

from __future__ import annotations

from mp.games.tictactoe.game import State, TicTacToeError, apply_move, new_state
from mp.games.tictactoe.session import TicTacToeGame, TicTacToeSession

TIC_TAC_TOE = TicTacToeGame()

__all__ = [
    "TIC_TAC_TOE",
    "TicTacToeGame",
    "TicTacToeSession",
    "State",
    "TicTacToeError",
    "apply_move",
    "new_state",
]
