"""FastAPI application entry point.

Wires together defaults, server state, the platform service, and the transport
layer, and exposes two routes:

- ``GET /health``  -- liveness probe.
- ``WS /ws``       -- the realtime channel.

The WebSocket endpoint owns only transport concerns: read a string, enforce
size/rate limits, decode and validate the envelope, hand the validated command
to the platform, and send whatever deliveries come back. No game rules appear
here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

from mp.config import DEFAULTS, Settings
from mp.domain.service import Platform
from mp.domain.state import ServerState
from mp.games import build_default_registry
from mp.protocol import messages
from mp.protocol.errors import ErrorCode
from mp.protocol.messages import Envelope, ErrorPayload, MessageType
from mp.storage import Store
from mp.transport.connection import Client
from mp.transport.manager import ConnectionRegistry

log = logging.getLogger("mp")
logging.basicConfig(level=logging.INFO)
# Types that mutate cross-cutting state and are therefore rate-limited.
_STATE_CHANGING = frozenset(
    {
        MessageType.CREATE_ROOM.value,
        MessageType.JOIN_ROOM.value,
        MessageType.LEAVE_ROOM.value,
        MessageType.FIND_MATCH.value,
        MessageType.CANCEL_MATCH.value,
        MessageType.START_GAME.value,
        MessageType.GAME_ACTION.value,
        MessageType.REMATCH.value,
        MessageType.REJOIN.value,
    }
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = ConnectionRegistry()

    async def deliver(delivery):
        # Push into a bound player's socket (used by background forfeit timers).
        target = registry.get(delivery.player_id)
        if target is not None:
            await target.send(delivery.encode())

    store = Store(app.state.settings.db_path) if app.state.settings.db_path else None

    state = ServerState()
    state.registry = build_default_registry()
    platform = Platform(state, app.state.settings, state.registry, deliver=deliver, store=store)
    app.state.platform = platform
    app.state.registry = registry
    app.state.server_state = state
    app.state.store = store
    try:
        yield
    finally:
        if store is not None:
            try:
                await asyncio.to_thread(store.close)
            except Exception:
                pass


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or DEFAULTS
    app = FastAPI(title="Multiplayer Platform (MVP)", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": "0.1.0"})

    @app.get("/history")
    async def history() -> JSONResponse:
        store: Store | None = app.state.store
        if store is None:
            return JSONResponse({"games": []})
        games = await asyncio.to_thread(store.recent_games, 20)
        return JSONResponse({"games": games})

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        settings = ws.app.state.settings
        platform: Platform = ws.app.state.platform
        registry: ConnectionRegistry = ws.app.state.registry
        client = Client(connection_id=secrets.token_hex(8), send=ws.send_json, settings=settings)
        log.info("ws open conn=%s", client.connection_id)

        try:
            while True:
                raw = await ws.receive_text()

                # Size limit, checked before any parsing.
                if len(raw) > settings.max_message_bytes:
                    if await _strike(ws, settings, client, ErrorCode.OVERSIZED_MESSAGE, "message too large"):
                        break
                    continue

                # Decode + validate the envelope.
                try:
                    env = _parse(raw)
                except Exception:
                    if await _strike(ws, settings, client, ErrorCode.MALFORMED_MESSAGE, "invalid JSON or envelope"):
                        break
                    continue

                # A player may only handshake once per connection (rejoin uses a
                # fresh connection, so it is allowed only when unbound).
                if env.type == MessageType.HELLO.value and client.player_id is not None:
                    await _send(ws, _error(ErrorCode.INVALID_ACTION, "already bound", env.seq))
                    continue

                # Rate-limit state-changing commands (legal but too fast -> not a strike).
                if env.type in _STATE_CHANGING and not client.limiter.allow():
                    await _send(ws, _error(ErrorCode.RATE_LIMITED, "too many commands", env.seq))
                    continue

                deliveries = platform.handle(env, client.player_id)

                # Bind identity before sending so self-deliveries route correctly.
                if client.player_id is None and env.type in (
                    MessageType.HELLO.value,
                    MessageType.REJOIN.value,
                ):
                    bind_target = _identity_from(deliveries, env)
                    if bind_target:
                        client.player_id = bind_target
                        registry.bind(client)

                for d in deliveries:
                    if client.player_id is None or d.player_id == client.player_id:
                        # Our own socket closed -> nothing more to do this loop.
                        if not await _deliver_to(client, d):
                            break
                    else:
                        peer = registry.get(d.player_id)
                        if peer is not None:
                            # A peer that just dropped must not kill this loop.
                            await _deliver_to(peer, d)

        except WebSocketDisconnect:
            log.info("ws disconnect conn=%s", client.connection_id)
        except Exception as exc:  # noqa: BLE001 -- never kill the loop without cleanup
            log.exception("ws error conn=%s: %s", client.connection_id, exc)
        finally:
            registry.unbind(client)
            if client.player_id is not None:
                # Inform the session/room and arm any forfeit timer; the returned
                # deliveries go to the remaining peers.
                for d in await platform.handle_disconnect(client.player_id):
                    peer = registry.get(d.player_id)
                    if peer is not None:
                        await _deliver_to(peer, d)
            log.info("ws close conn=%s", client.connection_id)

    return app


# --------------------------------------------------------------------------- #
# Transport helpers
# --------------------------------------------------------------------------- #


def _parse(raw: str) -> Envelope:
    return Envelope.model_validate(json.loads(raw))


def _identity_from(deliveries, env) -> str | None:
    """Determine the id to bind this connection to, from its deliveries.

    For ``hello`` the id is the one in the ``hello_ack``; for ``rejoin`` it is
    the requested ``player_id`` (only when the rejoin actually succeeded, i.e.
    the server produced a resync ``state_update``).
    """
    if env.type == MessageType.REJOIN.value:
        if any(d.type == MessageType.STATE_UPDATE for d in deliveries):
            pid = env.payload.get("player_id")
            return pid if isinstance(pid, str) and pid else None
        return None
    for d in deliveries:
        if d.type == MessageType.HELLO_ACK:
            return d.player_id
    return None


async def _deliver_to(client: Client, delivery) -> bool:
    """Send a delivery to a client, swallowing closed-socket errors.

    Returns True if it was sent, False if that client's socket is gone.
    """
    try:
        await client.send(delivery.encode())
        return True
    except WebSocketDisconnect:
        return False
    except Exception as exc:  # a peer dropping mid-send must not cascade
        log.debug("deliver failed conn=%s: %s", client.connection_id, exc)
        return False


async def _send(ws: WebSocket, message: dict) -> None:
    if ws.application_state == WebSocketState.CONNECTED:
        await ws.send_json(message)


def _error(code: str, message: str, seq: int | None = None) -> dict:
    return messages.outbound(MessageType.ERROR, ErrorPayload(code=code, message=message), seq)


async def _strike(ws, settings: Settings, client: Client, code: str, message: str) -> bool:
    """Send an error and record a protocol violation.

    Returns True when the connection has exceeded its strike budget and the
    caller should close it.
    """
    await _send(ws, _error(code, message))
    return client.take_strike() >= settings.max_dispatch_strikes


app = create_app()
