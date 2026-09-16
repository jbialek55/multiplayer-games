# Multiplayer Game Platform

An authoritative realtime platform for playing games with friends over the
web. **Games: Tic-Tac-Toe, Chess, and „1 z dziesięciu" (a Polish elimination
quiz).**

- Server is authoritative: clients send intents, never game state.
- Game logic is isolated from transport/room management behind a stable
  plugin contract, so new games can be added without touching the platform.
- No auth, no accounts, no database for the MVP: anyone who can reach the
  server can play. State lives in memory.

## Architecture (brief)

```
transport (WebSocket) -> protocol (wire schemas) -> domain (players, rooms,
           matchmaking, sessions)  ->  games (plug-in Game / GameSession)
```

Dependencies flow one way: `transport -> domain -> games.base`. Games never
import transport or domain; the platform never imports a specific game.

## Layout

```
server/   Python FastAPI backend (uv project) — src/mp
client/   Node.js frontend (Vite + TypeScript) — src/
docs/     architecture + protocol + workflow docs
```

## Run it (localhost)

**Backend** (in `server/`):

```powershell
uv sync
uv run uvicorn mp.main:app --reload      # http://127.0.0.1:8000
```

**Frontend** (in `client/`, second terminal):

```powershell
pnpm install
pnpm dev                                 # http://127.0.0.1:5173
```

`pnpm dev` proxies `/ws` and `/health` to the backend, so both use one origin
(no CORS). Open `http://127.0.0.1:5173` in two tabs (or a second browser) and:

1. Pick a game (Tic-Tac-Toe, Chess, or „1 z dziesięciu") in the lobby.
2. One tab **Create room** (or **Quick match** for 2-player games) and share
   the room code; the other tab **Join with a code**.
3. Fixed-size games auto-start when full; quiz is started by its **host** using
   **▶ Start game**.
4. Play. The server is authoritative and validates every move/answer. Chess
   shows the legal destinations of your selected piece.
5. Close a tab mid-game: in 2-player games the opponent is told and wins by
   forfeit after a grace window; reopen and hit **Rejoin game** (the app keeps
   your id/session in localStorage).
6. **Leave room** returns you to the lobby, clears your session, and (if the
   game was running) ends it for the remaining player.

## Tests

```powershell
cd server && uv run pytest -q
cd client && pnpm build                # also runs a type-check via tsc
```

## Protocol

See `docs/protocol.md` for the wire format, message types, and lifecycle/
reconnect semantics. The client mirrors the types in `client/src/protocol.ts`.

## Deployment (future VPS)

Single process behind a reverse proxy (e.g. Caddy) terminating TLS and
upgrading WebSockets; run uvicorn under systemd with auto-restart. Because
state is in-memory, there is exactly **one** server instance and a restart
drops active games — acceptable for the MVP. See `docs/architecture.md`.
