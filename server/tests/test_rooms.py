"""Room lifecycle tests (milestone 3: platform core without games)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def test_create_room(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        _hello(ws)
        ws.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        msg = ws.receive_json()
        assert msg["type"] == "room_created"
        room = msg["payload"]["room"]
        assert room["game_id"] == "tictactoe"
        assert room["status"] == "waiting"
        assert len(room["players"]) == 1  # host auto-joined


def test_join_room_notifies_peers(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        aid = _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            bid = _hello(b)

            with client.websocket_connect("/ws") as c:
                _hello(c)

            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            joined = b.receive_json()
            assert joined["type"] == "room_joined"
            assert bid in joined["payload"]["room"]["players"]

            # the host (a) is notified that the roster changed
            update = a.receive_json()
            assert update["type"] == "room_update"
            assert bid in update["payload"]["room"]["players"]


def test_join_missing_room_is_error(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        _hello(ws)
        ws.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": "nope"}})
        err = ws.receive_json()
        assert err["payload"]["code"] == "room_not_found"


def test_leave_room_updates_peers(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        aid = _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            bid = _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()   # room_joined
            b.receive_json()   # game_started (room reaches 2 players)
            a.receive_json()   # room_update from join
            a.receive_json()   # game_started

            b.send_json({"type": "leave_room", "seq": 3})
            left = b.receive_json()
            assert left["type"] == "room_left"
            assert left["payload"]["room_id"] == rid

            # A remains alone; the 2-player game ends and A wins by abandonment.
            over = a.receive_json()
            assert over["type"] == "game_over"
            assert over["payload"]["result"]["winner"] == aid
            assert over["payload"]["result"]["reason"] == "abandoned"


def test_cannot_be_in_two_rooms(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        _hello(ws)
        ws.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "a"}})
        ws.receive_json()
        # creating a second room while already in one -> error
        ws.send_json({"type": "create_room", "seq": 3, "payload": {"game_id": "b"}})
        err = ws.receive_json()
        assert err["payload"]["code"] == "already_in_room"


def test_list_rooms(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        a.receive_json()

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "list_rooms", "seq": 2})
            msg = b.receive_json()
            assert msg["type"] == "room_list"
            assert len(msg["payload"]["rooms"]) >= 1
