"""Pong session + realtime wiring tests."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from mp.games.pong.session import PongSession


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def test_input_moves_paddle() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    before = s.snapshot()["paddles"]["l"]
    s.handle_input("p1", {"dir": -1})
    for _ in range(20):
        s.tick()
    assert s.snapshot()["paddles"]["l"] < before  # left moved up


def test_realtime_updates_flow(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "pong"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b_start = b.receive_json()  # game_started
            assert b_start["type"] == "game_started"
            a.receive_json()  # room_update
            a_start = a.receive_json()  # game_started
            assert a_start["payload"]["state"]["ball"]

            # arrow input: left paddle up
            a.send_json({"type": "game_action", "seq": 3, "payload": {"action": {"dir": -1}}})

            # within a few ticks the server broadcasts state updates automatically.
            time.sleep(0.25)
            update = a.receive_json()
            assert update["type"] == "state_update"
            state = update["payload"]["state"]
            assert "ball" in state and "paddles" in state
            assert state["paddles"]["l"] < 50.0  # moved up from centre
