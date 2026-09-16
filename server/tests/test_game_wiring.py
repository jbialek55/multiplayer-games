"""Session wiring integration tests: room -> session -> state_update/game_over."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def _state(msg) -> dict:
    return msg["payload"]["state"]


def test_room_becomes_game_when_full(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        a_ = _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            b_ = _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            joined = b.receive_json()
            assert joined["type"] == "room_joined"
            # b's connection: room_joined, then auto-start
            b_start = b.receive_json()
            assert b_start["type"] == "game_started"
            assert b_start["payload"]["game_id"] == "tictactoe"

            # a sees room_update, then auto-start
            a_upd = a.receive_json()
            assert a_upd["type"] == "room_update"
            a_start = a.receive_json()
            assert a_start["type"] == "game_started"

            symbols = a_start["payload"]["state"]["symbols"]
            assert symbols[a_] == "X"
            assert symbols[b_] == "O"


def test_full_game_play_to_x_win(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b.receive_json()  # game_started
            a.receive_json()  # room_update
            a.receive_json()  # game_started

            def move(mover, other, cell, expect_over=False):
                mover.send_json(
                    {"type": "game_action", "seq": 3, "payload": {"action": {"cell": cell}}}
                )
                # every move broadcasts a state_update to BOTH players
                m = mover.receive_json()
                o = other.receive_json()
                assert m["type"] == "state_update"
                assert o["type"] == "state_update"
                if expect_over:
                    m_over = mover.receive_json()
                    o_over = other.receive_json()
                    assert m_over["type"] == "game_over"
                    assert o_over["type"] == "game_over"
                    return m_over

            # X (a) takes 0,4,8 ; O (b) takes 3,5
            move(a, b, 0)
            move(b, a, 3)
            move(a, b, 4)
            move(b, a, 5)
            over = move(a, b, 8, expect_over=True)
            assert over["payload"]["result"]["winner"] == "X"


def test_illegal_move_is_error_not_state_change(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b.receive_json()  # game_started
            a.receive_json()  # room_update
            a.receive_json()  # game_started

            # a (X) plays 0
            a.send_json({"type": "game_action", "seq": 3, "payload": {"action": {"cell": 0}}})
            a.receive_json()  # state_update
            b.receive_json()  # state_update

            # b (O) tries to take the same cell -> error, no state broadcast
            b.send_json({"type": "game_action", "seq": 3, "payload": {"action": {"cell": 0}}})
            err = b.receive_json()
            assert err["type"] == "error"
            assert err["payload"]["code"] == "invalid_action"


def test_action_before_game_is_error(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        # not in a room at all
        a.send_json({"type": "game_action", "seq": 2, "payload": {"action": {"cell": 0}}})
        err = a.receive_json()
        assert err["type"] == "error"
