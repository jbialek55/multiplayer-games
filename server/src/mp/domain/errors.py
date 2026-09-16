"""Domain exceptions for expected, user-facing failures.

``PlatformError`` maps directly to a structured ``error`` delivery and is the
signalled way a handler rejects a command without crashing the socket.
"""

from __future__ import annotations


class PlatformError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
