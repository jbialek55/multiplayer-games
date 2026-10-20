# Network Protocol

## Rules

- Treat every client message as untrusted input.
- Use explicit message types and schema validation.
- Include protocol/version information when compatibility is required.
- Make state-changing commands idempotent where practical.
- Define behavior for duplicate, delayed, reordered, malformed, and oversized messages.
- Define connection states: connecting, authenticated, lobby, matched, in-game, reconnecting, closed.
- Define reconnect semantics before implementing reconnect.
- Keep serialization/deserialization in the transport boundary.

## Wire format

One WebSocket per player. Every message is a JSON object with a uniform envelope:

```json
{ "type": "<message_type>", "seq": 3, "payload": { ... } }
```

- `type` selects the schema the payload is validated against.
- `seq` is a monotonic per-connection counter on client->server commands; the
  server echoes it back on the response(s) addressed to the sender. Peer
  fan-out messages carry no `seq`.
- `payload` is always an object (may be empty).

Serialization/deserialization lives at the transport boundary
(`mp/transport`), and the schemas are the single source of truth in
`mp/protocol/messages.py`. The client mirrors the types in
`client/src/protocol.ts`.

## Message types

Client -> server:

- `hello` `{ client_version }` — handshake; the server issues the player id.
- `rejoin` `{ player_id, session_id }` — resume a game after a disconnect; the
  server cancels any pending forfeit and resyncs every player with a full
  snapshot. Allowed on a fresh connection (before `hello`).
- `create_room` `{ game_id }` — create a room and auto-join the host.
- `join_room` `{ room_id }` — join an existing open room.
- `leave_room` `{ room_id? }` — leave the room (omit id to leave current).
- `list_rooms` `{}` — list open rooms.
- `find_match` `{ game_id }` — enter the per-game matchmaking queue (only
  2-player games).
- `cancel_match` `{}` — leave the matchmaking queue.
- `start_game` `{}` — the room **host** starts the game (required for
  variable-player games such as quiz); only valid when the room already holds
  `min_players..max_players`.
- `game_action` `{ action }` — an opaque, game-defined intent; the server
  validates and applies it. `action` is never authoritative state.
- `ping` `{ ts }` — keepalive; server replies `pong`.

Server -> client:

- `hello_ack` `{ player_id, protocol_version, server_time_ms }`
- `room_created` `{ room }`
- `room_joined` `{ room }`
- `room_left` `{ room_id }`
- `room_update` `{ room }` — sent to remaining members on roster change.
- `room_list` `{ rooms: [...] }`
- `queue_ack` `{ game_id, queued }` — matched the queue request (or cancel).
- `match_found` `{ room }` — two queued players were paired.
- `game_started` `{ game_id, session_id, players, state }` — a session began;
  sent to all seated players. The snapshot (with each player's role) is in
  `state`. A client stores `session_id` + its `player_id` to rejoin later.
- `state_update` `{ state }` — the full authoritative snapshot, broadcast after
  each validated action.
- `game_over` `{ state, result }` — the session finished. `result` is
  `{ winner, draw, reason?, winning_line? }`; `reason: "forfeit"` indicates a
  timeout forfeit (in which case `winner` is a player id).
- `peer_disconnected` `{ player_id }` — a session peer dropped (the opponent
  sees this and waits for the grace window).
- `peer_reconnected` `{ player_id }` — a session peer rejoined.
- `pong` `{ ts }`
- `error` `{ code, message }`

`room` is `{ id, game_id, host_id, players: [player_id], status }` where
`status` is `waiting | playing | closed`.

## Error codes

`malformed_message`, `unknown_type`, `oversized_message`, `rate_limited`,
`protocol_violation`, `not_in_room`, `room_not_found`, `room_full`,
`already_in_room`, `invalid_action`, `invalid_room_slot`, `internal`.

## Connection states

TCP -> `connecting` -> (`hello` ->) `lobby` <-> `in_room` `in_queue` `in_game`
-> `disconnected`. `disconnected` is a flag on the player, not a terminal
delete, so a later `rejoin` can resume.

## Lifecycle / typing notes

- A command before `hello` (or `rejoin`) is rejected with `invalid_action`.
- A second `hello` on one connection is rejected (`invalid_action`).
- A player may be in a room *or* the queue, never both.
- Matchmaking is a per-game FIFO queue for **2-player** games; the first two
  candidates form a room and the game auto-starts.
- A fixed-size game (Tic-Tac-Toe, Chess) auto-starts when the room is **full**
  (== `max_players`). A variable-size game (quiz, 2..10 players) is started by
  the **host** via `start_game` (auto-start only when it reaches `max_players`).
- State-changing commands (`create_room`, `join_room`, `leave_room`,
  `find_match`, `cancel_match`, `start_game`, `game_action`, `rejoin`) are
  rate-limited per connection.
- Malformed / oversized / unknown messages increment a strike counter; after
  `max_dispatch_strikes` (default 3) the server closes the connection.
- Game action errors (wrong turn, occupied cell, etc.) return an `error` with
  code `invalid_action`; they never close the socket.

## Disconnect / reconnect semantics

- On disconnect mid-game the player is marked `disconnected`, the opponent
  receives `peer_disconnected`, and a **grace window**
  (`reconnect_grace_seconds`, default 10s; 0 = instant) is armed. If the player
  does not `rejoin` in time, the game is **forfeited**: the opponent wins with
  `game_over` and `result.reason == "forfeit"`.
- On `rejoin` the server cancels the forfeit, rebinds the new socket, and
  resyncs **every** player with a full `state_update` (the opponent also gets
  `peer_reconnected`).
- On disconnect while in a waiting room, the player is removed like a normal
  leave; an empty room is destroyed. A queued player is removed from the queue.
