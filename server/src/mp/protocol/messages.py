"""Wire protocol schemas.

Every WebSocket message is a JSON object with a uniform envelope:

    {"type": "<message_type>", "seq": <int>, "payload": {...}}

- ``type`` selects the schema the payload is validated against.
- ``seq`` is a client-supplied correlation id, echoed back on the reply sent
  to that same client so it can match a response to the command it sent.
  It is *not* currently used for ordering or duplicate detection on the
  server — Platform.handle() only copies it onto outgoing Deliveries aimed
  at the original sender. Optional on client->server commands; omitted on
  server->client messages that aren't a direct reply.

Serialization/deserialization lives at the transport boundary. These schemas
are the single source of truth for the wire format and are mirrored on the
client in ``client/src/protocol.ts``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Callable

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Envelope
# --------------------------------------------------------------------------- #


class Envelope(BaseModel):
    """The outer wrapper for every message. Payload is validated separately by
    type so a missing/extra ``type`` is only ever rejected once."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    seq: Optional[int] = None
    payload: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Message types
# --------------------------------------------------------------------------- #


class MessageType(str, Enum):
    # client -> server
    HELLO = "hello"
    REJOIN = "rejoin"
    CREATE_ROOM = "create_room"
    JOIN_ROOM = "join_room"
    LEAVE_ROOM = "leave_room"
    LIST_ROOMS = "list_rooms"
    FIND_MATCH = "find_match"
    CANCEL_MATCH = "cancel_match"
    START_GAME = "start_game"
    GAME_ACTION = "game_action"
    REMATCH = "rematch"
    PING = "ping"

    # server -> client
    HELLO_ACK = "hello_ack"
    ROOM_CREATED = "room_created"
    ROOM_JOINED = "room_joined"
    ROOM_LEFT = "room_left"
    ROOM_UPDATE = "room_update"
    ROOM_LIST = "room_list"
    QUEUE_ACK = "queue_ack"
    MATCH_FOUND = "match_found"
    GAME_STARTED = "game_started"
    STATE_UPDATE = "state_update"
    GAME_OVER = "game_over"
    PEER_DISCONNECTED = "peer_disconnected"
    PEER_RECONNECTED = "peer_reconnected"
    REMATCH_REQUESTED = "rematch_requested"
    PONG = "pong"
    ERROR = "error"


# Keys used to find the payload model for a given (client) message type.
CLIENT_TYPES: dict[str, type[BaseModel]] = {}


def _register(type: str) -> Callable:
    def deco(model: type[BaseModel]) -> type[BaseModel]:
        CLIENT_TYPES[type] = model
        return model

    return deco


# --------------------------------------------------------------------------- #
# Client -> server payloads
# --------------------------------------------------------------------------- #


@_register(MessageType.HELLO.value)
class HelloPayload(BaseModel):
    """Handshake. No auth -- the server issues the player id."""

    model_config = ConfigDict(extra="forbid")
    client_version: str = "0.1.0"


@_register(MessageType.CREATE_ROOM.value)
class CreateRoomPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: str = Field(min_length=1, max_length=32)


@_register(MessageType.JOIN_ROOM.value)
class JoinRoomPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    room_id: str = Field(min_length=1, max_length=64)


@_register(MessageType.LEAVE_ROOM.value)
class LeaveRoomPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    room_id: Optional[str] = None  # None => leave current room


@_register(MessageType.LIST_ROOMS.value)
class ListRoomsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


@_register(MessageType.PING.value)
class PingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ts: int = 0


@_register(MessageType.FIND_MATCH.value)
class FindMatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: str = Field(min_length=1, max_length=32)


@_register(MessageType.CANCEL_MATCH.value)
class CancelMatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


@_register(MessageType.GAME_ACTION.value)
class GameActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: dict[str, Any] = Field(default_factory=dict)


@_register(MessageType.START_GAME.value)
class StartGamePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


@_register(MessageType.REMATCH.value)
class RematchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


@_register(MessageType.REJOIN.value)
class RejoinPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)


# --------------------------------------------------------------------------- #
# Server -> client payloads
# --------------------------------------------------------------------------- #


class RoomInfo(BaseModel):
    """Public view of a room. Never leaks internal references."""

    model_config = ConfigDict(frozen=True)
    id: str
    game_id: str
    host_id: str
    players: list[str]
    status: str  # "waiting" | "playing" | "closed"


class HelloAckPayload(BaseModel):
    player_id: str
    protocol_version: str
    server_time_ms: int


class RoomActionPayload(BaseModel):
    room: RoomInfo


class RoomLeftPayload(BaseModel):
    room_id: str


class RoomListPayload(BaseModel):
    rooms: list[RoomInfo]


class QueueAckPayload(BaseModel):
    game_id: str
    queued: bool


class MatchFoundPayload(BaseModel):
    room: RoomInfo


class GameStartedPayload(BaseModel):
    game_id: str
    session_id: str
    players: list[str]
    state: dict[str, Any]


class StateUpdatePayload(BaseModel):
    state: dict[str, Any]
    # Which game the snapshot belongs to. A client that just rejoined has no
    # room/game info yet and needs this to pick the right renderer.
    game_id: str | None = None


class GameOverPayload(BaseModel):
    state: dict[str, Any]
    result: dict[str, Any]


class PeerStatusPayload(BaseModel):
    player_id: str


class RematchRequestedPayload(BaseModel):
    player_id: str
    votes: int
    total: int


class PongPayload(BaseModel):
    ts: int


class ErrorPayload(BaseModel):
    code: str
    message: str


# Build the outbound message from a payload. Keeps message construction in one
# place so the wire format stays consistent.
def outbound(type: MessageType, payload: BaseModel, seq: Optional[int] = None) -> dict[str, Any]:
    return {"type": type.value, "seq": seq, "payload": payload.model_dump(mode="json")}
