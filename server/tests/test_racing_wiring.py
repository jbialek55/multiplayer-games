"""Racing session + realtime wiring tests."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from mp.games.base import GameError
from mp.games.racing.session import RacingGame, RacingSession


def test_requires_two_to_four_players() -> None:
    RacingGame().create_session(["a", "b"])
    with pytest.raises(GameError):
        RacingGame().create_session(["only"])
    with pytest.raises(GameError):
        RacingGame().create_session([f"p{i}" for i in range(5)])


def test_phases_and_countdown() -> None:
    s = RacingSession(["a", "b"])
    s.start()
    assert s.snapshot()["phase"] == "starting"
    assert s.snapshot()["countdown"] > 0
    s.countdown = 1
    s.tick()
    assert s.snapshot()["phase"] == "racing"


def test_snapshot_has_state() -> None:
    s = RacingSession(["a", "b"])
    s.start()
    snap = s.snapshot()
    assert snap["track"]["w"] == 36
    assert len(snap["cars"]) == 2
    assert len(snap["track"]["checkpoints"]) == 4
    assert snap["cars"][0]["lap"] == 0


def test_input_buffered_and_applies() -> None:
    s = RacingSession(["a", "b"])
    s.start()
    s.countdown = 1
    s.tick()  # racing
    s.handle_input("a", {"accel": True})
    before = s.snapshot()["cars"][0]["speed"]
    for _ in range(10):
        s.tick()
    assert s.snapshot()["cars"][0]["speed"] > before


def test_remove_player_keeps_racing() -> None:
    s = RacingSession(["a", "b", "c"])
    s.start()
    s.countdown = 1
    s.tick()
    events = s.remove_player("c")
    assert not s.snapshot()["finished"]
    assert len(s.snapshot()["cars"]) == 3
    assert s.snapshot()["cars"][2]["speed"] == 0  # leaver stopped


def test_realtime_updates_flow(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "racing"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined (racing does not auto-start at 2/4)
            a.receive_json()  # room_update

            a.send_json({"type": "start_game", "seq": 3})
            assert a.receive_json()["type"] == "game_started"
            assert b.receive_json()["type"] == "game_started"

            time.sleep(0.2)
            update = a.receive_json()
            assert update["type"] == "state_update"
            state = update["payload"]["state"]
            assert state["phase"] in ("starting", "racing")
            assert len(state["cars"]) == 2

            a.send_json(
                {"type": "game_action", "seq": 4, "payload": {"action": {"accel": True}}}
            )  # accepted, no error


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]
