"""Snake Battle session + realtime wiring tests."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from mp.games.base import GameError
from mp.games.snake.session import SnakeGame, SnakeSession


def test_requires_two_to_four_players() -> None:
    SnakeGame().create_session(["a", "b"])  # ok
    with pytest.raises(GameError):
        SnakeGame().create_session(["only"])
    with pytest.raises(GameError):
        SnakeGame().create_session([f"p{i}" for i in range(5)])


def test_phases_and_countdown() -> None:
    s = SnakeSession(["a", "b"])
    s.start()
    assert s.snapshot()["phase"] == "starting"
    assert s.snapshot()["countdown"] > 0
    s.countdown = 1
    s.tick()
    assert s.snapshot()["phase"] == "running"


def test_snapshot_has_state() -> None:
    s = SnakeSession(["a", "b"])
    s.start()
    snap = s.snapshot()
    assert snap["board"]["w"] == 20
    assert len(snap["snakes"]) == 2
    assert snap["snakes"][0]["alive"] is True
    assert len(snap["food"]) >= 1


def test_invalid_dir_rejected() -> None:
    s = SnakeSession(["a", "b"])
    s.start()
    with pytest.raises(GameError, match="dir must be"):
        s.handle_input("a", {"dir": "diagonal"})


def test_input_buffered_not_reversed() -> None:
    s = SnakeSession(["a", "b"])
    s.start()
    s.countdown = 1
    s.tick()  # running
    # a starts facing right; try to reverse left -> ignored by engine
    s.handle_input("a", {"dir": "left"})
    before = s.snapshot()["snakes"][0]["body"][0]
    s.tick()
    after = s.snapshot()["snakes"][0]["body"][0]
    assert after[0] > before[0]  # kept moving right


def test_remove_player_last_standing_wins() -> None:
    s = SnakeSession(["a", "b"])
    s.start()
    s.countdown = 1
    s.tick()
    events = s.remove_player("b")
    assert s.snapshot()["finished"]
    assert s.is_finished()  # the platform clears the session on this
    assert s.snapshot()["winner"] == "a"
    assert any(e.type == "over" for e in events)


def test_remove_player_continues_with_three() -> None:
    s = SnakeSession(["a", "b", "c"])
    s.start()
    s.countdown = 1
    s.tick()
    events = s.remove_player("c")
    assert not s.snapshot()["finished"]
    assert len(s.snapshot()["snakes"]) == 3
    assert s.snapshot()["snakes"][2]["alive"] is False


def test_realtime_updates_flow(client: TestClient) -> None:
    with client.websocket_connect("/ws") as a:
        _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "snake"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined (snake does NOT auto-start at 2/4)
            a.receive_json()  # room_update

            a.send_json({"type": "start_game", "seq": 3})
            assert a.receive_json()["type"] == "game_started"
            assert b.receive_json()["type"] == "game_started"

            # the server pushes state updates automatically
            time.sleep(0.25)
            update = a.receive_json()
            assert update["type"] == "state_update"
            state = update["payload"]["state"]
            assert state["phase"] in ("starting", "running")
            assert len(state["snakes"]) == 2

            # directional input is accepted without error
            a.send_json({"type": "game_action", "seq": 4, "payload": {"action": {"dir": "down"}}})


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]
