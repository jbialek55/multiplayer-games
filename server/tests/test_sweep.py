"""Memory hygiene: players who never come back (and rooms only they kept alive) are freed."""

from __future__ import annotations

import asyncio

from mp.config import Settings
from mp.domain.service import Platform
from mp.domain.state import ServerState
from mp.games import build_default_registry
from mp.protocol.messages import LeaveRoomPayload

GRACE = 10.0


def _platform() -> Platform:
    state = ServerState()
    state.registry = build_default_registry()
    return Platform(state, Settings(reconnect_grace_seconds=GRACE), state.registry)


def _room_with(p: Platform, game_id: str, n: int) -> tuple[list[str], str]:
    ids = [p.state.new_player(addr="").id for _ in range(n)]
    room = p.state.create_room(ids[0], game_id)
    for pid in ids:
        room.add_player(pid)
        p.state.players[pid].current_room_id = room.id
    return ids, room.id


def _drop(p: Platform, pid: str, at: float) -> None:
    asyncio.run(p.handle_disconnect(pid))
    p.state.players[pid].disconnected_at = at


def test_player_who_never_joined_a_room_is_freed_after_the_grace_window() -> None:
    p = _platform()
    pid = p.state.new_player(addr="").id
    _drop(p, pid, at=100.0)
    p.sweep(now=100.0 + GRACE)  # still inside grace + slack
    assert pid in p.state.players
    p.sweep(now=100.0 + GRACE + 6)
    assert pid not in p.state.players


def test_connected_players_are_never_swept() -> None:
    p = _platform()
    pid = p.state.new_player(addr="").id
    p.sweep(now=10**9)
    assert pid in p.state.players


def test_abandoned_quiz_room_and_session_are_removed() -> None:
    async def scenario() -> None:
        p = _platform()
        ids, rid = _room_with(p, "quiz", 3)
        room = p.state.rooms[rid]
        p._start_session(room)  # a running quiz nobody is watching any more
        assert room.session_id in p.state.sessions
        for pid in ids:
            await p.handle_disconnect(pid)
            p.state.players[pid].disconnected_at = 100.0
        p.sweep(now=1000.0)
        assert rid not in p.state.rooms
        assert not p.state.sessions
        assert not any(pid in p.state.players for pid in ids)

    asyncio.run(scenario())


def test_forfeited_duel_does_not_leave_a_room_behind() -> None:
    p = _platform()
    (winner, loser), rid = _room_with(p, "tictactoe", 2)
    room = p.state.rooms[rid]
    room.session_id = None  # the duel already ended by forfeit; only the roster is left
    _drop(p, loser, at=100.0)
    # handle_disconnect already removed the loser from a finished room; make the
    # old leak explicit: the loser is still on the roster
    room.add_player(loser)
    p.state.players[loser].current_room_id = rid
    p.sweep(now=1000.0)
    assert loser not in p.state.players and loser not in room.players
    assert rid in p.state.rooms  # the winner is still there
    # ...and once the winner leaves too, the room goes away
    p._leave_room(winner, LeaveRoomPayload(), None)
    assert rid not in p.state.rooms


def test_room_keeps_running_while_someone_else_is_still_connected() -> None:
    async def scenario() -> None:
        p = _platform()
        ids, rid = _room_with(p, "quiz", 3)
        p._start_session(p.state.rooms[rid])
        await p.handle_disconnect(ids[2])
        p.state.players[ids[2]].disconnected_at = 100.0
        p.sweep(now=1000.0)
        assert rid in p.state.rooms and p.state.rooms[rid].session_id is not None
        assert ids[2] in p.state.players  # retried on a later sweep, once the game is over

    asyncio.run(scenario())
