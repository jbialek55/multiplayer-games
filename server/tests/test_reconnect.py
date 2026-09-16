"""Disconnect / reconnect / forfeit integration tests."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def _hello(ws) -> str:
    ws.send_json({"type": "hello", "seq": 1})
    return ws.receive_json()["payload"]["player_id"]


def _start_game(client) -> tuple[str, str]:
    """Create a room and seat a second player; return (player_id, session_id)."""
    with client.websocket_connect("/ws") as a:
        aid = _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b_start = b.receive_json()  # game_started
            a.receive_json()  # room_update
            a.receive_json()  # game_started
            return aid, b_start["payload"]["session_id"]


def test_rejoin_resyncs_after_disconnect(grace_client: TestClient) -> None:
    # helper closes its socket at the end, so A disconnects inside _start_game.
    aid, sid = _start_game(grace_client)
    # A (the caller) reconnects and rejoins the same session; it must be told
    # the current board (default: empty). We verify a resync snapshot arrives.
    with grace_client.websocket_connect("/ws") as a2:
        a2.send_json({"type": "rejoin", "seq": 1, "payload": {"player_id": aid, "session_id": sid}})
        state = a2.receive_json()
        assert state["type"] == "state_update"
        assert state["payload"]["state"]["symbols"]
        assert state["payload"]["state"]["board"] == [None] * 9


def test_opponent_notified_on_disconnect_and_reconnect(grace_client: TestClient) -> None:
    # B stays connected (outer); A is the inner connection so we can drop it and
    # watch B receive the disconnect / reconnect notifications + resync.
    with grace_client.websocket_connect("/ws") as b:
        bid = _hello(b)
        with grace_client.websocket_connect("/ws") as a:
            aid = _hello(a)
            a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
            rid = a.receive_json()["payload"]["room"]["id"]
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b_start = b.receive_json()  # game_started
            sid = b_start["payload"]["session_id"]
            a.receive_json()  # room_update
            a.receive_json()  # game_started

            # A plays 0 (X), then A's socket closes (end of this with-block).
            a.send_json({"type": "game_action", "seq": 3, "payload": {"action": {"cell": 0}}})
            a.receive_json()  # own state_update
            b.receive_json()  # peer state_update

        # A is now disconnected; B was told.
        disc = b.receive_json()
        assert disc["type"] == "peer_disconnected"
        assert disc["payload"]["player_id"] == aid

        # A reconnects and rejoins within the long grace window.
        with grace_client.websocket_connect("/ws") as a2:
            a2.send_json(
                {"type": "rejoin", "seq": 1, "payload": {"player_id": aid, "session_id": sid}}
            )
            a2.receive_json()  # state_update (resync) to the reconnecting player
            rec = b.receive_json()
            assert rec["type"] == "peer_reconnected"
            assert rec["payload"]["player_id"] == aid
            b_state = b.receive_json()
            assert b_state["type"] == "state_update"
            assert b_state["payload"]["state"]["board"][0] == "X"  # A's earlier move


def test_forfeit_after_grace_window(forfeit_client: TestClient) -> None:
    # B stays connected (outer); A is inner and drops out -> B wins on timeout.
    with forfeit_client.websocket_connect("/ws") as b:
        bid = _hello(b)
        with forfeit_client.websocket_connect("/ws") as a:
            aid = _hello(a)
            a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
            rid = a.receive_json()["payload"]["room"]["id"]
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b.receive_json()  # game_started
            a.receive_json()  # room_update
            a.receive_json()  # game_started

        # A's socket closes -> B is told, then the tiny grace window expires.
        disc = b.receive_json()
        assert disc["type"] == "peer_disconnected"

        time.sleep(0.35)  # > grace=0.1s
        over = b.receive_json()
        assert over["type"] == "game_over"
        assert over["payload"]["result"]["winner"] == bid
        assert over["payload"]["result"]["reason"] == "forfeit"


def test_rejoin_unknown_player_is_error(grace_client: TestClient) -> None:
    with grace_client.websocket_connect("/ws") as a2:
        a2.send_json(
            {"type": "rejoin", "seq": 1, "payload": {"player_id": "nope", "session_id": "nope"}}
        )
        err = a2.receive_json()
        assert err["type"] == "error"


def test_rejoin_when_already_connected_is_error(grace_client: TestClient) -> None:
    with grace_client.websocket_connect("/ws") as a:
        aid = _hello(a)
        a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
        rid = a.receive_json()["payload"]["room"]["id"]

        with grace_client.websocket_connect("/ws") as b:
            _hello(b)
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            sid = b.receive_json()["payload"]["session_id"]  # game_started
            a.receive_json()  # room_update
            a.receive_json()  # game_started

            # A is still connected on its own socket; a rejoin from a2 must fail.
            with grace_client.websocket_connect("/ws") as a2:
                a2.send_json(
                    {"type": "rejoin", "seq": 1, "payload": {"player_id": aid, "session_id": sid}}
                )
                err = a2.receive_json()
                assert err["type"] == "error"


def test_rejoin_unknown_session_is_error(grace_client: TestClient) -> None:
    with grace_client.websocket_connect("/ws") as a:
        aid = _hello(a)
        # A is connected, so rejoin is rejected by the connected check first;
        # use a disconnected, valid player for a bad-session probe instead.
    with grace_client.websocket_connect("/ws") as a2:
        a2.send_json(
            {"type": "rejoin", "seq": 1, "payload": {"player_id": aid, "session_id": "bogus"}}
        )
        err = a2.receive_json()
        assert err["type"] == "error"


def test_no_move_after_forfeit(forfeit_client: TestClient) -> None:
    with forfeit_client.websocket_connect("/ws") as b:
        bid = _hello(b)
        with forfeit_client.websocket_connect("/ws") as a:
            _hello(a)
            a.send_json({"type": "create_room", "seq": 2, "payload": {"game_id": "tictactoe"}})
            rid = a.receive_json()["payload"]["room"]["id"]
            b.send_json({"type": "join_room", "seq": 2, "payload": {"room_id": rid}})
            b.receive_json()  # room_joined
            b.receive_json()  # game_started
            a.receive_json()  # room_update
            a.receive_json()  # game_started

        b.receive_json()  # peer_disconnected
        time.sleep(0.35)
        over = b.receive_json()
        assert over["type"] == "game_over"

        # The game is over (forfeit): a further move is rejected.
        b.send_json({"type": "game_action", "seq": 3, "payload": {"action": {"cell": 0}}})
        err = b.receive_json()
        assert err["type"] == "error"
