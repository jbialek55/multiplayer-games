"""Basic WebSocket hello handshake / ping-pong test (the milestone-1 'echo')."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_hello_acknowledged(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "seq": 1})
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"
        assert ack["seq"] == 1  # echoed back to the sender
        assert ack["payload"]["player_id"]
        assert ack["payload"]["protocol_version"]


def test_ping_pong(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "seq": 1})
        ws.receive_json()  # hello_ack
        ws.send_json({"type": "ping", "seq": 2, "payload": {"ts": 123}})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert pong["seq"] == 2  # correlated to the command
        assert pong["payload"]["ts"] == 123
