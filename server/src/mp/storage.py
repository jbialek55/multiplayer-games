"""SQLite persistence for completed games.

Only *finished* games are written here; live room/session state stays in RAM
for the realtime tick. Writes/reads run off the event loop (via
``asyncio.to_thread`` in the caller) so the game tick never blocks on I/O --
see the architecture invariant "persistence is outside the realtime tick".

A single :class:`Store` is created at startup and guarded by a lock; all access
happens from the thread pool, never on the tick path.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id   TEXT    NOT NULL,
    players   TEXT    NOT NULL,            -- JSON array of player ids
    winner    TEXT,                        -- player id or NULL
    result    TEXT    NOT NULL,            -- JSON of the game result
    played_at TEXT    NOT NULL             -- ISO timestamp (UTC)
);
"""


class Store:
    def __init__(self, path: str) -> None:
        if path == ":memory:":
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def record_game(self, game_id: str, players: list[str], result: dict[str, Any]) -> None:
        winner = result.get("winner")
        with self._lock:
            self._conn.execute(
                "INSERT INTO games (game_id, players, winner, result, played_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    game_id,
                    json.dumps(players),
                    winner,
                    json.dumps(result),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()

    def recent_games(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, game_id, players, winner, result, played_at"
                " FROM games ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "game_id": row[1],
                "players": json.loads(row[2]),
                "winner": row[3],
                "result": json.loads(row[4]),
                "played_at": row[5],
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
