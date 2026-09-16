"""Tic-Tac-Toe session tests: lifecycle, turn enforcement, invalid input."""

from __future__ import annotations

import pytest

from mp.games.base import GameError
from mp.games.tictactoe.session import TicTacToeGame, TicTacToeSession

P1 = "p1"  # X
P2 = "p2"  # O


def make_session() -> TicTacToeSession:
    return TicTacToeSession([P1, P2])


def test_symbols_assigned_in_order() -> None:
    s = make_session()
    assert s.role_of(P1) == "X"
    assert s.role_of(P2) == "O"


def test_cannot_move_before_start() -> None:
    s = make_session()
    with pytest.raises(GameError, match="not started"):
        s.handle_input(P1, {"cell": 0})


def test_first_snapshot_after_start() -> None:
    s = make_session()
    events = s.start()
    assert s.started
    # start emits an initial state event
    assert any(e.type == "state" for e in events)
    snap = s.snapshot()
    assert snap["board"] == [None] * 9
    assert snap["whos_turn"] == P1
    assert snap["symbols"] == {P1: "X", P2: "O"}


def test_other_player_cannot_move() -> None:
    s = make_session()
    s.start()
    with pytest.raises(GameError, match="not that player"):
        s.handle_input(P2, {"cell": 0})  # O tries to move first


def test_move_updates_board_and_turn() -> None:
    s = make_session()
    s.start()
    events = s.handle_input(P1, {"cell": 0})
    assert any(e.type == "state" for e in events)
    assert s.snapshot()["board"][0] == "X"
    assert s.snapshot()["whos_turn"] == P2


def test_occupied_cell_rejected() -> None:
    s = make_session()
    s.start()
    s.handle_input(P1, {"cell": 0})
    with pytest.raises(GameError, match="already taken"):
        s.handle_input(P2, {"cell": 0})


def test_out_of_range_cell_rejected() -> None:
    s = make_session()
    s.start()
    with pytest.raises(GameError):
        s.handle_input(P1, {"cell": 42})


def test_non_participant_rejected() -> None:
    s = make_session()
    s.start()
    with pytest.raises(GameError, match="not a participant"):
        s.handle_input("stranger", {"cell": 0})


def test_win_emits_game_over() -> None:
    s = make_session()
    s.start()
    seq = [(P1, 0), (P2, 3), (P1, 4), (P2, 5), (P1, 8)]
    for pid, cell in seq:
        events = s.handle_input(pid, {"cell": cell})
    over = [e for e in events if e.type == "over"]
    assert len(over) == 1
    assert s.is_finished()
    assert s.result()["winner"] == "X"
    assert s.result()["winning_line"] == [0, 4, 8]


def test_cannot_move_after_game_over() -> None:
    s = make_session()
    s.start()
    for pid, cell in ((P1, 0), (P2, 3), (P1, 4), (P2, 5), (P1, 8)):
        s.handle_input(pid, {"cell": cell})
    with pytest.raises(GameError, match="game is over"):
        s.handle_input(P1, {"cell": 1})


def test_game_factory_creates_session() -> None:
    game = TicTacToeGame()
    assert game.id == "tictactoe"
    assert game.max_players == 2
    assert isinstance(game.create_session([P1, P2]), TicTacToeSession)
    with pytest.raises(GameError):
        game.create_session([P1])  # needs exactly 2
