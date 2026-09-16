"""Wiring tests for chess play and host-started (variable-size) games."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def test_chess_move_plays_end_to_end(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        aid = _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "chess"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            bid = _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b_start = b.receive_json()  # game_started (2-player auto-start)
            assert b_start["type"] == "game_started"
            a.receive_json()  # room_update
            a_start = a.receive_json()  # game_started
            assert a_start["payload"]["state"]["symbols"][aid] == "white"
            assert a_start["payload"]["state"]["symbols"][bid] == "black"

            # white (a) plays e2->e4
            a.send_json(
                {"type": "game_action", "seq": 3, "payload": {"action": {"from": "e2", "to": "e4"}}}
            )
            a_state = a.receive_json()
            assert a_state["type"] == "state_update"
            b.receive_json()  # peer state_update
            board = a_state["payload"]["state"]["board"]
            assert board[4][4] == "P"  # e4
            assert board[6][4] is None  # e2 vacated
            assert a_state["payload"]["state"]["legal_moves"]


def test_illegal_chess_move_is_error(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "chess"}})
        rid = a.receive_json()["payload"]["room"]["id"]
        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json(); b.receive_json()
            a.receive_json(); a.receive_json()
            # black (b) moves first -> error "not your move"
            b.send_json(
                {"type": "game_action", "seq": 3, "payload": {"action": {"from": "e7", "to": "e5"}}}
            )
            err = b.receive_json()
            assert err["type"] == "error"


def test_quiz_host_starts_after_join(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        aid = _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "quiz"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            bid = _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined (quiz does NOT auto-start at 2/10)
            a.receive_json()  # room_update
            # not started yet
            a.send_json({"type": "start_game", "seq": 3})
            a_start = a.receive_json()
            b_start = b.receive_json()
            assert a_start["type"] == "game_started"
            assert b_start["type"] == "game_started"
            state = a_start["payload"]["state"]
            assert state["current"] == aid
            assert state["question"]["options"]

            # a (current) answers -> advances to b
            a.send_json({"type": "game_action", "seq": 4, "payload": {"action": {"answer": 0}}})
            next_state = a.receive_json()
            assert next_state["type"] == "state_update"
            b.receive_json()
            assert next_state["payload"]["state"]["current"] == bid


def test_rematch_after_game_over(client: TestClient) -> None:
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

            def move(mover, other, cell):
                mover.send_json(
                    {"type": "game_action", "seq": 3, "payload": {"action": {"cell": cell}}}
                )
                assert mover.receive_json()["type"] == "state_update"
                assert other.receive_json()["type"] == "state_update"

            # X (a) wins: 0,4,8 ; O (b): 3,5
            move(a, b, 0)
            move(b, a, 3)
            move(a, b, 4)
            move(b, a, 5)
            a.send_json({"type": "game_action", "seq": 3, "payload": {"action": {"cell": 8}}})
            assert a.receive_json()["type"] == "state_update"
            assert a.receive_json()["type"] == "game_over"
            assert b.receive_json()["type"] == "state_update"
            assert b.receive_json()["type"] == "game_over"

            # rematch must be confirmed by all players
            a.send_json({"type": "rematch", "seq": 4})
            # both are notified of the request (votes 1/2)
            assert a.receive_json()["type"] == "rematch_requested"
            assert b.receive_json()["type"] == "rematch_requested"

            # b confirms -> votes 2/2 -> a new game starts for both
            b.send_json({"type": "rematch", "seq": 4})
            assert b.receive_json()["type"] == "rematch_requested"
            assert a.receive_json()["type"] == "rematch_requested"
            assert a.receive_json()["type"] == "game_started"
            assert b.receive_json()["type"] == "game_started"


def test_non_host_cannot_start(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "quiz"}})
        rid = a.receive_json()["payload"]["room"]["id"]
        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()
            a.receive_json()
            b.send_json({"type": "start_game", "seq": 3})
            err = b.receive_json()
            assert err["type"] == "error"
