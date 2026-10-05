"""Domain orchestration.

This is the application/domain boundary: it owns room and player lifecycle
rules, mutates ``ServerState``, and returns transport-neutral ``Delivery``
instructions. It never imports transport -- it only knows "who to tell and
what to say", not how a socket works.

Dependency direction (preserved):  domain -> protocol.  Never transport.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from mp.config import Settings
from mp.domain.errors import PlatformError
from mp.domain.rooms import RoomStatus
from mp.domain.state import ServerState, new_public_id
from mp.games.base import GameError, GameEvent
from mp.games.registry import GameRegistry
from mp.protocol.delivery import Delivery
from mp.protocol import messages
from mp.protocol.errors import ErrorCode
from mp.protocol.messages import (
    CancelMatchPayload,
    CreateRoomPayload,
    ErrorPayload,
    FindMatchPayload,
    GameActionPayload,
    GameOverPayload,
    GameStartedPayload,
    HelloAckPayload,
    JoinRoomPayload,
    LeaveRoomPayload,
    ListRoomsPayload,
    MatchFoundPayload,
    MessageType,
    PongPayload,
    PingPayload,
    QueueAckPayload,
    RejoinPayload,
    RoomActionPayload,
    RoomLeftPayload,
    RoomListPayload,
    StateUpdatePayload,
    StartGamePayload,
    PeerStatusPayload,
    RematchRequestedPayload,
)

log = logging.getLogger("mp")


def _err(origin: str, code: str, message: str, seq: int | None = None) -> Delivery:
    return Delivery(origin, MessageType.ERROR, ErrorPayload(code=code, message=message), seq)


class Platform:
    """Turns a validated client command into state mutations + deliveries."""

    def __init__(
        self,
        state: ServerState,
        settings: Settings,
        registry: GameRegistry,
        deliver: Callable[[Delivery], Awaitable[None]] | None = None,
        store: Any | None = None,
    ) -> None:
        self.state = state
        self.settings = settings
        self.registry = registry or state.registry
        # ``deliver`` pushes an unsolicited message to whoever is bound to that
        # player (used by background forfeit timers). Injected by the transport
        # so the platform stays transport-agnostic.
        self.deliver = deliver or _noop_deliver
        # Optional SQLite store; completed games are written here.
        self.store = store
        # player_id -> running forfeit task.
        self._forfeit_tasks: dict[str, asyncio.Task] = {}
        # session_id -> realtime tick loop task.
        self._tick_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #
    def handle(self, env: messages.Envelope, origin: str | None) -> list[Delivery]:
        """Validate ``env`` and route it to the matching handler.

        ``origin`` is the player id bound to the connection (``None`` before
        the handshake). Returns the deliveries to send. Raises nothing --
        expected failures are converted into ``error`` deliveries.
        """
        log.debug("recv %s from %s", env.type, origin)

        payload_model = messages.CLIENT_TYPES.get(env.type)
        if payload_model is None:
            return [
                _err(
                    origin or "",
                    ErrorCode.UNKNOWN_TYPE,
                    f"unknown message type: {env.type}",
                    env.seq,
                )
            ]

        try:
            payload = payload_model.model_validate(env.payload)
        except Exception as exc:  # pydantic.ValidationError and subclasses
            return [
                _err(
                    origin or "",
                    ErrorCode.MALFORMED_MESSAGE,
                    f"invalid payload: {exc}",
                    env.seq,
                )
            ]

        # Handshake (or a reconnect) is all that is allowed before binding.
        if origin is None and env.type not in (MessageType.HELLO.value, MessageType.REJOIN.value):
            return [_err("", ErrorCode.INVALID_ACTION, "must hello first", env.seq)]

        try:
            deliveries = self._dispatch(origin or "", env.type, payload, env.seq)
        except PlatformError as exc:
            return [_err(origin or "", exc.code, exc.message, env.seq)]
        except GameError as exc:
            # Illegal game play is a per-command error, never a socket kill.
            return [_err(origin or "", ErrorCode.INVALID_ACTION, str(exc), env.seq)]
        except Exception:  # unexpected -> never crash the socket
            log.exception("unhandled error dispatching %s for origin=%s", env.type, origin)
            return [_err(origin or "", ErrorCode.INTERNAL, "internal error", env.seq)]

        # Correlate the command's seq only to messages for the originator.
        for d in deliveries:
            if d.player_id == (origin or "") and d.seq is None:
                d.seq = env.seq
        return deliveries

    # ------------------------------------------------------------------ #
    # Dispatch table
    # ------------------------------------------------------------------ #
    def _dispatch(self, origin: str, type: str, payload, seq: int | None) -> list[Delivery]:
        handler = {
            MessageType.HELLO.value: self._hello,
            MessageType.CREATE_ROOM.value: self._create_room,
            MessageType.JOIN_ROOM.value: self._join_room,
            MessageType.LEAVE_ROOM.value: self._leave_room,
            MessageType.LIST_ROOMS.value: self._list_rooms,
            MessageType.FIND_MATCH.value: self._find_match,
            MessageType.CANCEL_MATCH.value: self._cancel_match,
            MessageType.START_GAME.value: self._start_game,
            MessageType.GAME_ACTION.value: self._game_action,
            MessageType.REMATCH.value: self._rematch,
            MessageType.REJOIN.value: self._rejoin,
            MessageType.PING.value: self._ping,
        }[type]
        return handler(origin, payload, seq)

    # ------------------------------------------------------------------ #
    # Handlers
    # ------------------------------------------------------------------ #
    def _hello(self, origin: str, payload, seq: int | None) -> list[Delivery]:
        player = self.state.new_player(addr=origin)
        player.connected = True
        ack = HelloAckPayload(
            player_id=player.id,
            protocol_version="0.1.0",
            server_time_ms=_now_ms(),
        )
        # The origin is unbound, so we must set seq explicitly here.
        return [Delivery(player.id, MessageType.HELLO_ACK, ack, seq)]

    def _create_room(self, origin: str, payload: CreateRoomPayload, seq) -> list[Delivery]:
        if self._current_room(origin) is not None:
            raise PlatformError(ErrorCode.ALREADY_IN_ROOM, "already in a room")
        if len(self.state.rooms) >= self.settings.max_rooms:
            raise PlatformError(ErrorCode.INVALID_ACTION, "server room limit reached")

        room = self.state.create_room(host_id=origin, game_id=payload.game_id)
        self.state.players[origin].current_room_id = room.id
        return [Delivery(origin, MessageType.ROOM_CREATED, RoomActionPayload(room=room.info()))]

    def _join_room(self, origin: str, payload: JoinRoomPayload, seq) -> list[Delivery]:
        if self._current_room(origin) is not None:
            raise PlatformError(ErrorCode.ALREADY_IN_ROOM, "already in a room")
        room = self.state.rooms.get(payload.room_id)
        if room is None:
            raise PlatformError(ErrorCode.ROOM_NOT_FOUND, "room not found")
        if not room.is_open():
            raise PlatformError(ErrorCode.INVALID_ACTION, "room is not open")

        room.add_player(origin)
        self.state.players[origin].current_room_id = room.id
        deliveries: list[Delivery] = [
            Delivery(origin, MessageType.ROOM_JOINED, RoomActionPayload(room=room.info()))
        ]
        deliveries.extend(_notify_others(room, origin))
        deliveries.extend(self._maybe_start(room))
        return deliveries

    def _leave_room(self, origin: str, payload: LeaveRoomPayload, seq) -> list[Delivery]:
        current = self._current_room(origin)
        if current is None:
            raise PlatformError(ErrorCode.NOT_IN_ROOM, "not in a room")
        if payload.room_id is not None and payload.room_id != current.id:
            raise PlatformError(ErrorCode.NOT_IN_ROOM, "not in that room")

        room = self.state.rooms[current.id]
        deliveries: list[Delivery] = [
            Delivery(origin, MessageType.ROOM_LEFT, RoomLeftPayload(room_id=room.id))
        ]

        # If the room hosts an active game, handle the leaver:
        #  - multi-player games (quiz): remove them and keep playing.
        #  - duels (2-player): the game can't continue, so the remaining player wins.
        remaining = [p for p in room.players if p != origin]
        game = self.registry.get(room.game_id)
        is_multi = game is not None and game.max_players > 2
        if room.session_id is not None:
            session = self.state.sessions.get(room.session_id)
            if session is not None and not session.is_finished():
                if is_multi:
                    events = session.remove_player(origin)
                    deliveries.extend(self._events_to_deliveries(session, events))
                    if session.is_finished():
                        self._close_session(room.session_id, room, result=session.result())
                else:
                    session.mark_finished(remaining[0] if remaining else None, "abandoned")
                    result = {"winner": remaining[0] if remaining else None, "reason": "abandoned"}
                    self._close_session(room.session_id, room, result=result)
                    for pid in remaining:
                        deliveries.append(
                            Delivery(
                                pid,
                                MessageType.GAME_OVER,
                                GameOverPayload(
                                    state=session.snapshot(),
                                    result={"winner": pid, "reason": "abandoned"},
                                ),
                            )
                        )

        room.remove_player(origin)
        room.rematch_votes.clear()
        self.state.players[origin].current_room_id = None
        if not room.players:
            self.state.rooms.pop(room.id, None)
        elif room.session_id is None:
            # Not an active game: notify the remaining peers of the roster change.
            deliveries.extend(_notify_others(room, origin))
        return deliveries

    def _list_rooms(self, origin: str, payload: ListRoomsPayload, seq) -> list[Delivery]:
        return [
            Delivery(
                origin,
                MessageType.ROOM_LIST,
                RoomListPayload(rooms=self.state.live_rooms()),
            )
        ]

    def _ping(self, origin: str, payload: PingPayload, seq) -> list[Delivery]:
        return [Delivery(origin, MessageType.PONG, PongPayload(ts=payload.ts))]

    def _rejoin(self, origin: str, payload: RejoinPayload, seq) -> list[Delivery]:
        player = self.state.players.get(payload.player_id)
        if player is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "unknown player")
        if player.connected:
            raise PlatformError(ErrorCode.INVALID_ACTION, "player already connected")
        session = self.state.sessions.get(payload.session_id)
        if session is None or payload.player_id not in session.player_ids:
            raise PlatformError(ErrorCode.INVALID_ACTION, "no active session for player")

        player.connected = True
        player.disconnected_at = None
        self._cancel_forfeit(payload.player_id)

        # Notify peers that the opponent is back, then resync everyone.
        deliveries: list[Delivery] = _notify_peers(
            session, payload.player_id, MessageType.PEER_RECONNECTED
        )
        for pid in session.player_ids:
            deliveries.append(
                Delivery(
                    pid,
                    MessageType.STATE_UPDATE,
                    StateUpdatePayload(state=session.snapshot(), game_id=session.game_id),
                )
            )
        # The rejoining client has lost its room info (code, host, game): send
        # it right after the resync snapshot (which must stay the first message).
        room = self._current_room(payload.player_id)
        if room is not None:
            deliveries.append(
                Delivery(payload.player_id, MessageType.ROOM_UPDATE, RoomActionPayload(room=room.info()))
            )
        return deliveries

    def _find_match(self, origin: str, payload: FindMatchPayload, seq) -> list[Delivery]:
        if self._current_room(origin) is not None:
            raise PlatformError(ErrorCode.ALREADY_IN_ROOM, "already in a room")
        game = self.registry.get(payload.game_id)
        if game is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, f"unknown game: {payload.game_id}")
        if game.max_players != 2:
            raise PlatformError(
                ErrorCode.INVALID_ACTION, "quick match is only for 2-player games"
            )

        opponent = self.state.pop_opponent(payload.game_id)
        if opponent is None:
            # No one waiting: enqueue and report.
            self.state.enqueue(payload.game_id, origin)
            return [
                Delivery(
                    origin,
                    MessageType.QUEUE_ACK,
                    QueueAckPayload(game_id=payload.game_id, queued=True),
                )
            ]

        # Pair the two players into a fresh room; the host is the waiter.
        room = self.state.create_room(host_id=opponent, game_id=payload.game_id)
        room.add_player(origin)
        room.add_player(opponent)
        self.state.players[origin].current_room_id = room.id
        self.state.players[opponent].current_room_id = room.id

        deliveries: list[Delivery] = [
            Delivery(origin, MessageType.MATCH_FOUND, MatchFoundPayload(room=room.info())),
            Delivery(opponent, MessageType.MATCH_FOUND, MatchFoundPayload(room=room.info())),
        ]
        deliveries.extend(self._maybe_start(room))
        return deliveries

    def _cancel_match(self, origin: str, payload: CancelMatchPayload, seq) -> list[Delivery]:
        game_id = self.state.is_queued(origin)
        if game_id is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "not in matchmaking queue")
        self.state.dequeue_player(origin)
        return [
            Delivery(
                origin, MessageType.QUEUE_ACK, QueueAckPayload(game_id=game_id, queued=False)
            )
        ]

    def _start_game(self, origin: str, payload: StartGamePayload, seq) -> list[Delivery]:
        room = self._current_room(origin)
        if room is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "not in a room")
        if room.host_id != origin:
            raise PlatformError(ErrorCode.INVALID_ACTION, "only the room host can start")
        if room.session_id is not None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "game already started")
        game = self.registry.get(room.game_id)
        if game is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "unknown game")
        n = len(room.players)
        if n < game.min_players:
            raise PlatformError(ErrorCode.INVALID_ACTION, f"need at least {game.min_players} players")
        if n > game.max_players:
            raise PlatformError(ErrorCode.INVALID_ACTION, f"at most {game.max_players} players")
        return self._start_session(room)

    def _rematch(self, origin: str, payload, seq) -> list[Delivery]:
        """Vote-based rematch: starts only when every connected player agrees.
        Notifies the other players that a rematch was requested."""
        room = self._current_room(origin)
        if room is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "not in a room")
        if room.session_id is not None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "game still in progress")
        game = self.registry.get(room.game_id)
        if game is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "unknown game")

        active = [
            p
            for p in room.players
            if self.state.players.get(p) is not None and self.state.players[p].connected
        ]
        if len(active) < game.min_players:
            raise PlatformError(
                ErrorCode.INVALID_ACTION, f"need at least {game.min_players} players to rematch"
            )

        room.rematch_votes.add(origin)
        votes = [p for p in room.rematch_votes if p in active]

        deliveries: list[Delivery] = [
            Delivery(
                pid,
                MessageType.REMATCH_REQUESTED,
                RematchRequestedPayload(player_id=origin, votes=len(votes), total=len(active)),
            )
            for pid in active
        ]
        if len(votes) >= len(active):
            room.rematch_votes.clear()
            room.status = RoomStatus.WAITING
            deliveries.extend(self._start_session(room))
        return deliveries

    def _game_action(self, origin: str, payload: GameActionPayload, seq) -> list[Delivery]:
        room = self._current_room(origin)
        if room is None or room.session_id is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "not in a running game")
        session = self.state.sessions.get(room.session_id)
        if session is None:
            raise PlatformError(ErrorCode.INVALID_ACTION, "session no longer active")
        if origin not in session.player_ids:
            raise PlatformError(ErrorCode.INVALID_ACTION, "not a participant")
        if not session.started or session.is_finished():
            raise PlatformError(ErrorCode.INVALID_ACTION, "game not in progress")

        events = session.handle_input(origin, payload.action)
        if session.is_finished():
            self._close_session(room.session_id, room, result=session.result())
        return self._events_to_deliveries(session, events)

    # ------------------------------------------------------------------ #
    # Game wiring
    # ------------------------------------------------------------------ #
    def _maybe_start(self, room) -> list[Delivery]:
        """Auto-start a session when the room is *full* (== max players).

        Used for fixed-size games (e.g. chess/tictactoe at 2 players);
        variable-size games (quiz) are started by the host via ``start_game``.
        """
        game = self.registry.get(room.game_id)
        if game is None or room.session_id is not None:
            return []
        if len(room.players) < game.min_players:
            return []
        if len(room.players) < game.max_players:
            return []
        return self._start_session(room)

    def _start_session(self, room) -> list[Delivery]:
        """Actually create + start a session for a ready room (min <= players <= max)."""
        game = self.registry.get(room.game_id)
        session = game.create_session(list(room.players))
        session_id = new_public_id()
        self.state.sessions[session_id] = session
        room.start(session_id)
        session.start()
        if session.rate is not None:
            # Realtime game: run a background tick loop that broadcasts state.
            self._tick_tasks[session_id] = asyncio.create_task(
                self._run_ticks(session_id)
            )
        return [
            Delivery(
                pid,
                MessageType.GAME_STARTED,
                GameStartedPayload(
                    game_id=room.game_id,
                    session_id=session_id,
                    players=list(room.players),
                    state=session.snapshot(),
                ),
            )
            for pid in room.players
        ]

    async def _run_ticks(self, session_id: str) -> None:
        """Background realtime loop: tick a realtime game and broadcast state."""
        room = self._room_of_session(session_id)
        session = self.state.sessions.get(session_id)
        if session is None:
            return
        # Schedule ticks against a monotonic deadline instead of ``sleep(rate)``
        # after the work: the latter adds the processing + send time to every
        # tick, so the game ran slow and the ticks arrived unevenly (visible as
        # stutter). If we ever fall far behind, re-anchor instead of bursting.
        interval = session.rate or 0.03
        loop = asyncio.get_running_loop()
        deadline = loop.time() + interval
        while True:
            await asyncio.sleep(max(0.0, deadline - loop.time()))
            deadline += interval
            if deadline < loop.time() - 5 * interval:
                deadline = loop.time() + interval
            if session.is_finished() or self.state.sessions.get(session_id) is not session:
                break
            events = session.tick()
            for d in self._events_to_deliveries(session, events):
                await self.deliver(d)
            # Re-check identity: a player may have left (and closed the session)
            # while we were awaiting the deliveries above.
            if session.is_finished() and self.state.sessions.get(session_id) is session:
                self._close_session(session_id, room, result=session.result())
                break
        self._tick_tasks.pop(session_id, None)

    def _room_of_session(self, session_id: str):
        for room in self.state.rooms.values():
            if room.session_id == session_id:
                return room
        return None

    def _close_session(self, session_id: str, room, result: dict | None = None) -> None:
        """Mark a session over: cancel its tick loop, drop it, and persist it."""
        session = self.state.sessions.get(session_id)
        game_id = session.game_id if session is not None else room.game_id
        players = list(session.player_ids) if session is not None else list(room.players)
        outcome = (
            result
            if result is not None
            else (session.result() if session is not None else {})
        )
        if room is not None:
            room.status = RoomStatus.CLOSED
            room.session_id = None
        self.state.sessions.pop(session_id, None)
        task = self._tick_tasks.pop(session_id, None)
        # The tick loop closes its own session when the game ends, so never
        # cancel the task we are currently running in.
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
        if self.store is not None and players:
            asyncio.create_task(self._persist_game(game_id, players, outcome))

    async def _persist_game(self, game_id: str, players: list[str], result: dict) -> None:
        """Write a finished game to the store off the event loop."""
        try:
            await asyncio.to_thread(self.store.record_game, game_id, players, result)
        except Exception:  # never let persistence break the game
            pass

    def _events_to_deliveries(self, session, events) -> list[Delivery]:
        """Map game events to per-player wire messages."""
        out: list[Delivery] = []
        for ev in events:
            if ev.type == GameEvent.STATE:
                for pid in session.player_ids:
                    out.append(
                        Delivery(
                            pid,
                            MessageType.STATE_UPDATE,
                            StateUpdatePayload(state=session.snapshot(), game_id=session.game_id),
                        )
                    )
            elif ev.type == GameEvent.OVER:
                for pid in session.player_ids:
                    out.append(
                        Delivery(
                            pid,
                            MessageType.GAME_OVER,
                            GameOverPayload(state=session.snapshot(), result=session.result()),
                        )
                    )
        return out

    # ------------------------------------------------------------------ #
    # Disconnect / reconnect / forfeit
    # ------------------------------------------------------------------ #
    async def handle_disconnect(self, player_id: str) -> list[Delivery]:
        """Handle a player dropping off (called by the transport on close).

        Returns deliveries for remaining peers. An active game arms a forfeit
        timer; a player just sitting in a waiting room is removed like a leave.
        """
        player = self.state.players.get(player_id)
        if player is None:
            return []
        player.connected = False
        player.disconnected_at = time.monotonic()
        self.state.dequeue_player(player_id)

        room = self.state.rooms.get(player.current_room_id) if player.current_room_id else None
        if room is None or room.session_id is None:
            # Not in a running game: remove from a waiting room, if any.
            if room is not None:
                room.remove_player(player_id)
                player.current_room_id = None
                if not room.players:
                    self.state.rooms.pop(room.id, None)
                return _notify_others(room, player_id)
            return []

        session = self.state.sessions.get(room.session_id)
        if session is None or session.is_finished():
            return []
        session_id = room.session_id
        peers = [p for p in session.player_ids if p != player_id]

        # Forfeit timers make sense for 2-player duels. For larger games
        # (e.g. quiz) a dropped player just sits out; they do not end everyone's
        # game, so we do not arm a timer.
        if len(session.player_ids) == 2:
            task = asyncio.create_task(self._forfeit_after(room, session, session_id, player_id))
            self._forfeit_tasks[player_id] = task

        return [
            Delivery(p, MessageType.PEER_DISCONNECTED, PeerStatusPayload(player_id=player_id))
            for p in peers
        ]

    async def _forfeit_after(self, room, session, session_id: str, loser_id: str) -> None:
        """If the player hasn't reconnected within the grace window, forfeit."""
        try:
            await asyncio.sleep(self.settings.reconnect_grace_seconds)
            player = self.state.players.get(loser_id)
            if session.is_finished():
                return
            if player is not None and player.connected:
                return  # reconnected in time; rejoin cancels, but double-check.

            winner = next((p for p in session.player_ids if p != loser_id), None)
            if winner is None:
                return
            session.mark_finished(winner, "forfeit")
            result = {"winner": winner, "reason": "forfeit"}
            self._close_session(session_id, room, result=result)
            for pid in session.player_ids:
                if pid == loser_id:
                    continue
                await self.deliver(
                    Delivery(
                        pid,
                        MessageType.GAME_OVER,
                        GameOverPayload(state=session.snapshot(), result=result),
                    )
                )
        finally:
            self._forfeit_tasks.pop(loser_id, None)

    # ------------------------------------------------------------------ #
    # Memory hygiene
    # ------------------------------------------------------------------ #
    async def run_sweeper(self) -> None:
        """Background loop: periodically free players who never came back."""
        while True:
            await asyncio.sleep(self.settings.sweep_interval_seconds)
            try:
                self.sweep()
            except Exception:  # a bug here must never kill the loop
                log.exception("sweep failed")

    def sweep(self, now: float | None = None) -> None:
        """Forget players that dropped and stayed away past the reconnect window.

        Without this, every connection that ever said hello stays in
        ``state.players`` forever, and rooms whose players all vanished (an
        abandoned quiz, a forfeited duel) keep counting against ``max_rooms``.
        """
        now = time.monotonic() if now is None else now
        # + a little slack so forfeit timers (which fire at the grace) run first
        cutoff = now - (self.settings.reconnect_grace_seconds + 5.0)
        gone = [
            p
            for p in self.state.players.values()
            if not p.connected and p.disconnected_at is not None and p.disconnected_at <= cutoff
        ]
        for player in gone:
            self._forget_player(player)

    def _forget_player(self, player) -> None:
        self._cancel_forfeit(player.id)
        self.state.dequeue_player(player.id)
        room = self.state.rooms.get(player.current_room_id) if player.current_room_id else None
        if room is not None:
            if room.session_id is not None and any(self._is_connected(p) for p in room.players):
                return  # a game is still running for others: try again next sweep
            room.remove_player(player.id)
            room.rematch_votes.discard(player.id)
            if not room.players:
                self._drop_room(room)
        self.state.players.pop(player.id, None)

    def _is_connected(self, player_id: str) -> bool:
        p = self.state.players.get(player_id)
        return p is not None and p.connected

    def _drop_room(self, room) -> None:
        """Remove an empty room together with any session/tick loop it still owns."""
        if room.session_id is not None:
            self.state.sessions.pop(room.session_id, None)
            task = self._tick_tasks.pop(room.session_id, None)
            if task is not None and not task.done():
                task.cancel()
            room.session_id = None
        self.state.rooms.pop(room.id, None)

    def _cancel_forfeit(self, player_id: str) -> None:
        task = self._forfeit_tasks.pop(player_id, None)
        if task is not None and not task.done():
            task.cancel()

    # ------------------------------------------------------------------ #
    def _current_room(self, player_id: str):
        player = self.state.players.get(player_id)
        if player is None or player.current_room_id is None:
            return None
        return self.state.rooms.get(player.current_room_id)


def _notify_others(room, origin: str) -> list[Delivery]:
    """Send a ``room_update`` to every current member except ``origin``."""
    return [
        Delivery(pid, MessageType.ROOM_UPDATE, RoomActionPayload(room=room.info()))
        for pid in room.players
        if pid != origin
    ]


def _notify_peers(session, player_id: str, type: MessageType) -> list[Delivery]:
    """Notify every session player except ``player_id`` about that player."""
    return [
        Delivery(pid, type, PeerStatusPayload(player_id=player_id))
        for pid in session.player_ids
        if pid != player_id
    ]


async def _noop_deliver(delivery: Delivery) -> None:
    return None


def _now_ms() -> int:
    return int(time.time() * 1000)
