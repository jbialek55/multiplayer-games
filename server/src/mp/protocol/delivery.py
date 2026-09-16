"""Transport-neutral outbound instruction.

``Delivery`` is produced by platform handlers and consumed by the WebSocket
endpoint. It is defined here (not in transport or platform) so that both sides
can depend on it without either depending on the other: platform -> protocol
and transport -> protocol are both allowed, while platform <-> transport must
never import each other.
"""

from __future__ import annotations

from typing import Any, Optional

from mp.protocol import messages
from mp.protocol.messages import MessageType


class Delivery:
    """A message addressed to one player, ready to encode and send."""

    __slots__ = ("player_id", "type", "payload", "seq")

    def __init__(
        self,
        player_id: str,
        type: MessageType,
        payload: messages.BaseModel,
        seq: Optional[int] = None,
    ) -> None:
        self.player_id = player_id
        self.type = type
        self.payload = payload
        self.seq = seq  # only set when correlating to the command's seq

    def encode(self) -> dict[str, Any]:
        return messages.outbound(self.type, self.payload, self.seq)
