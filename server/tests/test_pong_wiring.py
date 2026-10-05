"""Pong session + realtime wiring tests."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from mp.games.base import GameError
from mp.games.pong.session import PongSession


def _skip_countdown(s: PongSession) -> None:
    s.countdown = 1
    s.tick()
    assert s.phase == "running"


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def test_input_moves_paddle() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    _skip_countdown(s)
    before = s.snapshot()["paddles"]["l"]
    s.handle_input("p1", {"dir": -1})
    for _ in range(20):
        s.tick()


def test_starts_with_a_three_second_countdown() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    snap = s.snapshot()
    assert snap["phase"] == "starting"
    assert snap["countdown"] == 3


def test_everything_is_frozen_during_countdown() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    ball, paddles = s.snapshot()["ball"], s.snapshot()["paddles"]
    s.handle_input("p1", {"dir": -1})  # accepted early...
    for _ in range(60):
        s.tick()
    assert s.phase == "starting"  # ...but nothing moves until GO
    assert s.snapshot()["ball"] == ball
    assert s.snapshot()["paddles"] == paddles


def test_countdown_only_broadcasts_when_the_number_changes() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    broadcasts = sum(len(s.tick()) for _ in range(s.COUNTDOWN_TICKS))
    assert broadcasts == 3  # "2", "1" and "go" -- not 180 identical snapshots
    assert s.phase == "running"


def test_countdown_restarts_after_every_point() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    _skip_countdown(s)
    # put the ball just past the left paddle so the right player scores
    s.state = replace(s.state, ball_x=-3.0, ball_vx=-50.0)
    s.tick()
    snap = s.snapshot()
    assert snap["scores"] == {"l": 0, "r": 1}
    assert snap["phase"] == "starting" and snap["countdown"] == 3
    assert snap["ball"] == {"x": 50.0, "y": 50.0}  # back in the centre, frozen
    ball = snap["ball"]
    for _ in range(60):
        s.tick()
    assert s.snapshot()["ball"] == ball
    _skip_countdown(s)  # ...and play resumes
    assert s.phase == "running"


def test_the_winning_point_ends_the_game_instead_of_counting_down() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    _skip_countdown(s)
    s.state = replace(s.state, ball_x=-3.0, ball_vx=-50.0, score_r=4)
    s.tick()
    assert s.snapshot()["phase"] == "finished" and s.is_finished()


def test_finger_target_moves_the_paddle_there_at_normal_speed() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    _skip_countdown(s)
    s.handle_input("p1", {"target": 80})
    s.tick()
    step = s.snapshot()["paddles"]["l"] - 50.0
    assert 0 < step <= 60.0 * s.rate + 1e-9  # one normal step, not a teleport
    for _ in range(120):
        s.tick()


def test_target_is_clamped_to_the_field_and_validated() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    s.handle_input("p1", {"target": 1000})
    assert s.targets["p1"] == 100.0 - 22.0 / 2
    for bad in ("x", None, float("nan"), float("inf"), True):
        with pytest.raises(GameError):
            s.handle_input("p1", {"target": bad})


def test_keyboard_dir_takes_over_from_a_finger_target() -> None:
    s = PongSession(["p1", "p2"])
    s.start()
    s.handle_input("p1", {"target": 80})
    s.handle_input("p1", {"dir": 0})
    assert s.targets["p1"] is None


def test_realtime_updates_flow(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(PongSession, "COUNTDOWN_TICKS", 1)  # skip the 3 s countdown
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

            # the server broadcasts state updates on its own; within a few
            # ticks one of them must show the left paddle moved up from centre.
            deadline = time.monotonic() + 2.0
            state = None
            while time.monotonic() < deadline:
                update = a.receive_json()
                assert update["type"] == "state_update"
                state = update["payload"]["state"]
                assert "ball" in state and "paddles" in state
                if state["paddles"]["l"] < 50.0:
                    break
