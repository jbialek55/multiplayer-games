"""Error codes carried on the wire.

A server->client ``error`` message uses one of these codes and a human-readable
message. The set is closed on purpose so clients can match on codes and the
server can document them once, in ``docs/protocol.md``.
"""

from __future__ import annotations


class ErrorCode:
    # Well-formed message, but an expected precondition was not met.
    NOT_IN_ROOM = "not_in_room"
    ROOM_NOT_FOUND = "room_not_found"
    ROOM_FULL = "room_full"
    ALREADY_IN_ROOM = "already_in_room"
    INVALID_ACTION = "invalid_action"
    INVALID_ROOM_SLOT = "invalid_room_slot"

    # Malformed / hostile inbound data.
    MALFORMED_MESSAGE = "malformed_message"
    UNKNOWN_TYPE = "unknown_type"
    OVERSIZED_MESSAGE = "oversized_message"
    RATE_LIMITED = "rate_limited"
    PROTOCOL_VIOLATION = "protocol_violation"

    # Internal.
    INTERNAL = "internal"

    # A closed set for documentation/testing.
    ALL = frozenset(
        {
            NOT_IN_ROOM,
            ROOM_NOT_FOUND,
            ROOM_FULL,
            ALREADY_IN_ROOM,
            INVALID_ACTION,
            INVALID_ROOM_SLOT,
            MALFORMED_MESSAGE,
            UNKNOWN_TYPE,
            OVERSIZED_MESSAGE,
            RATE_LIMITED,
            PROTOCOL_VIOLATION,
            INTERNAL,
        }
    )
