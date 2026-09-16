"""Matchmaking integration tests over WebSocket."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def test_find_match_waits_when_no_opponent(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "find_match", "seq": 2, "payload": {"game_id": "tictactoe"}})
        ack = a.receive_json()
        assert ack["type"] == "queue_ack"
        assert ack["payload"]["queued"] is True
        assert ack["payload"]["game_id"] == "tictactoe"


def test_find_match_pairs_two_players(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "find_match", "seq": 2, "payload": {"game_id": "tictactoe"}})
        a.receive_json()  # queue_ack (queued)

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "find_match", "seq": 2, "payload": {"game_id": "tictactoe"}})
            b_match = b.receive_json()
            assert b_match["type"] == "match_found"
            b_start = b.receive_json()
            assert b_start["type"] == "game_started"

            a_match = a.receive_json()
            assert a_match["type"] == "match_found"
            a_start = a.receive_json()
            assert a_start["type"] == "game_started"

            # both are in the same room and game
            assert a_match["payload"]["room"]["id"] == b_match["payload"]["room"]["id"]
            assert a_start["payload"]["game_id"] == "tictactoe"
            assert a_start["payload"]["state"]["symbols"]


def test_cancel_match(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "find_match", "seq": 2, "payload": {"game_id": "tictactoe"}})
        a.receive_json()  # queue_ack (queued)
        a.send_json({"type": "cancel_match", "seq": 3})
        ack = a.receive_json()
        assert ack["type"] == "queue_ack"
        assert ack["payload"]["queued"] is False


def test_unknown_game_is_error(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "find_match", "seq": 2, "payload": {"game_id": "bogus"}})
        err = a.receive_json()
        assert err["type"] == "error"
