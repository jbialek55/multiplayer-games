"""Protocol robustness tests: hostile and malformed inputs."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_unknown_type_is_error(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "totally_bogus", "seq": 1})
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["payload"]["code"] == "unknown_type"


def test_malformed_payload_is_error(client: TestClient) -> None:
    # create_room requires game_id; missing payload must be rejected.
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "create_room", "seq": 2, "payload": {}})
        err = ws.receive_json()
        assert err["payload"]["code"] == "malformed_message"


def test_garbage_json_is_error(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_text("not json at all")
        err = ws.receive_json()
        assert err["payload"]["code"] == "malformed_message"


def test_oversized_message_is_error(small_client: TestClient) -> None:
    with small_client.websocket_connect("/ws") as ws:
        ws.send_text("x" * 1000)  # exceeds max_message_bytes=200
        err = ws.receive_json()
        assert err["payload"]["code"] == "oversized_message"


def test_command_before_hello_is_rejected(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "list_rooms", "seq": 1})
        err = ws.receive_json()
        assert err["payload"]["code"] == "invalid_action"


def test_rate_limited_when_too_fast(rate_client: TestClient) -> None:
    with rate_client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "seq": 1})
        ws.receive_json()  # hello_ack (hello is not state-changing, no tokens used)

        # capacity = 2 -> first two create_room pass, third is rate-limited.
        for i in (2, 3):
            ws.send_json({"type": "create_room", "seq": i, "payload": {"game_id": "tictactoe"}})
            ws.receive_json()
        ws.send_json({"type": "create_room", "seq": 4, "payload": {"game_id": "tictactoe"}})
        err = ws.receive_json()
        assert err["payload"]["code"] == "rate_limited"
