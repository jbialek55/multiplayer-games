"""SQLite persistence tests: finished games are written and readable."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def _win_tictactoe(client: TestClient) -> None:
    """Play a tic-tac-toe game to a checkmate-free win so it ends."""
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

            move(a, b, 0)
            move(b, a, 3)
            move(a, b, 4)
            move(b, a, 5)
            a.send_json({"type": "game_action", "seq": 3, "payload": {"action": {"cell": 8}}})
            a.receive_json()  # state_update
            a.receive_json()  # game_over
            b.receive_json()  # state_update
            b.receive_json()  # game_over


def test_finished_game_is_persisted(persist_client: TestClient) -> None:
    _win_tictactoe(persist_client)
    time.sleep(0.2)  # let the async DB write finish
    resp = persist_client.get("/history")
    assert resp.status_code == 200
    games = resp.json()["games"]
    assert len(games) >= 1
    latest = games[0]
    assert latest["game_id"] == "tictactoe"
    assert len(latest["players"]) == 2
    assert latest["winner"]  # a winner was recorded
    assert latest["played_at"]


def test_disabled_store_returns_empty(client: TestClient) -> None:
    # the default ``client`` fixture runs with persistence disabled
    resp = client.get("/history")
    assert resp.status_code == 200
    assert resp.json()["games"] == []
