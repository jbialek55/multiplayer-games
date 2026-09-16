# Architecture

## Target topology

gateway
  -> connection/auth
  -> lobby
  -> matchmaking
  -> game-session manager
  -> authoritative game sessions
  -> persistence/async workers

## Ownership

- Gateway owns transport concerns.
- Auth owns identity/session credentials.
- Lobby owns room membership.
- Matchmaking owns player-to-match decisions.
- GameSession owns authoritative game state and lifecycle.
- A game implementation owns its rules/state transitions.
- Persistence is outside the realtime tick.

## Core invariants

1. The server is authoritative.
2. Clients send commands/intents, not final state.
3. A game session is the single owner of its mutable game state.
4. Transport code must not contain game rules.
5. Game logic must not depend directly on WebSocket implementation details.
6. Blocking I/O is forbidden in the realtime tick.
7. Reconnect behavior is explicit, tested behavior.
8. Protocol messages are versioned when compatibility matters.

## Pluggable game contract

Stable boundary (implemented in `server/src/mp/games/base.py`):

- `Game` — static descriptor (`id`, `min/max_players`, `create_session()`).
- `GameSession` — one running game: `start()`, `handle_input()`,
  `snapshot()`, `result()`, `is_finished()`, `mark_finished()`,
  `on_player_disconnect()/reconnect()`.
- `GameEvent` — semantic events a game returns; the platform maps them to wire
  messages. A game never sends messages.
- `GameError` — illegal play reported back to the acting player as an `error`.

Exact names are implementation choices; ownership and dependency direction are
not: `transport -> domain -> games.base`, and games import neither transport
nor domain.

## Domain decisions (external to games)

- Forfeiting on timeout is a **platform/network policy**, not a game rule, so
  the platform calls `mark_finished()` and composes the `game_over` result
  itself; games never decide forfeit.
- The platform pushes unsolicited messages (e.g. a forfeit `game_over`) via an
  injected `deliver(delivery)` callable, keeping it transport-agnostic while
  still allowing background work (asyncio timers) to reach a socket.
