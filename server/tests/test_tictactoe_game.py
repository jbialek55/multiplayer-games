"""Exhaustive Tic-Tac-Toe pure-rule tests (deterministic, no I/O)."""

from __future__ import annotations

import pytest

from mp.games.tictactoe.game import O, X, TicTacToeError, apply_move, new_state, winning_line


def test_new_state_is_empty_and_x_moves_first() -> None:
    s = new_state()
    assert s.board == (None,) * 9
    assert s.turn == X
    assert not s.is_finished


def test_moves_alternate_player() -> None:
    s = apply_move(new_state(), X, 0)
    assert s.board[0] == X
    assert s.turn == O
    s2 = apply_move(s, O, 1)
    assert s2.board[1] == O
    assert s2.turn == X


def test_x_wins_on_diagonal() -> None:
    s = new_state()
    for sym, cell in ((X, 0), (O, 3), (X, 4), (O, 5), (X, 8)):
        s = apply_move(s, sym, cell)
    assert s.is_finished
    assert s.winner == X
    assert winning_line(s) == (0, 4, 8)


def test_o_wins_on_row() -> None:
    s = new_state()
    for sym, cell in ((X, 3), (O, 0), (X, 6), (O, 1), (X, 7), (O, 2)):
        s = apply_move(s, sym, cell)
    assert s.winner == O
    assert s.is_finished


def test_draw_when_board_full() -> None:
    # Fill all 9 cells with no winning line -> draw. Verified: no intermediate
    # move creates a line.
    s = new_state()
    seq = [(X, 0), (O, 2), (X, 1), (O, 4), (X, 6), (O, 3), (X, 5), (O, 8), (X, 7)]
    for sym, cell in seq:
        s = apply_move(s, sym, cell)
        assert s.winner is None  # nobody wins at any point
    assert s.draw
    assert s.winner is None
    assert s.is_finished
    assert s.board == (X, X, O, O, O, X, X, X, O)


def test_out_of_range_cell_rejected() -> None:
    with pytest.raises(TicTacToeError):
        apply_move(new_state(), X, 9)
    with pytest.raises(TicTacToeError):
        apply_move(new_state(), X, -1)


def test_occupied_cell_rejected() -> None:
    s = apply_move(new_state(), X, 4)
    with pytest.raises(TicTacToeError):
        apply_move(s, O, 4)  # O's turn but cell taken


def test_wrong_player_rejected() -> None:
    with pytest.raises(TicTacToeError):
        apply_move(new_state(), O, 0)  # X moves first


def test_invalid_symbol_rejected() -> None:
    with pytest.raises(TicTacToeError):
        apply_move(new_state(), "Z", 0)


def test_move_after_finish_rejected() -> None:
    s = new_state()
    for sym, cell in ((X, 0), (O, 3), (X, 4), (O, 5), (X, 8)):
        s = apply_move(s, sym, cell)
    assert s.winner == X
    with pytest.raises(TicTacToeError):
        apply_move(s, O, 1)


def test_state_is_immutable() -> None:
    s = new_state()
    s2 = apply_move(s, X, 0)
    assert s.board[0] is None  # original untouched
    assert s2.board[0] == X
