import { WsConnection } from "./net/ws";
import { state, subscribe } from "./state";
import { STORAGE, type Envelope, type RoomInfo, type GameSnapshot } from "./protocol";
import { GAME_RENDERERS, GAME_NAMES, QUICK_MATCH_GAMES, type RenderCtx } from "./games";
import { resetChess } from "./games/chess/render";
import { resetBoard } from "./games/tictactoe/render";

const conn = new WsConnection();

// True between sending a `rejoin` on connect and knowing it worked. If the
// server rejects it (stale session after a restart/ended game), we fall back to
// a fresh `hello` so the connection is never left unbound.
let rejoinPending = false;

// Last pong direction we told the server. We only send when it *changes*, so
// OS key-repeat doesn't flood the connection with identical inputs.
let lastPongDir = 0;

// --- elements ---------------------------------------------------------------
function byId(id: string): HTMLElement | null {
  return document.getElementById(id);
}

const statusEl = byId("status") as HTMLDivElement;
const noticeEl = byId("notice") as HTMLDivElement;
const lobbyEl = byId("lobby") as HTMLElement;
const gameEl = byId("game") as HTMLElement;
const boardEl = byId("board") as HTMLDivElement;
const mySymEl = byId("my-symbol") as HTMLElement;
const turnEl = byId("turn") as HTMLDivElement;
const resultEl = byId("result") as HTMLDivElement;
const roomListEl = byId("room-list") as HTMLDivElement;
const roomCardEl = byId("roomcard") as HTMLDivElement;
const lobbyCodeEl = byId("lobby-code") as HTMLSpanElement;
const roomWaitingEl = byId("room-waiting") as HTMLSpanElement;
const roomMetaEl = byId("room-meta") as HTMLSpanElement;
const toastEl = byId("toast") as HTMLDivElement;
const joinCodeInput = byId("join-code") as HTMLInputElement;

// --- persistence ------------------------------------------------------------
function read<T>(key: string): T | null {
  const raw = localStorage.getItem(key);
  return raw ? (JSON.parse(raw) as T) : null;
}
function write(key: string, value: string): void {
  localStorage.setItem(key, JSON.stringify(value));
}
function clear(key: string): void {
  localStorage.removeItem(key);
}

// --- feedback ---------------------------------------------------------------
let toastTimer: number | undefined;
function flash(text: string): void {
  toastEl.textContent = text;
  toastEl.classList.add("show");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toastEl.classList.remove("show"), 1800);
}
function setNotice(text: string | null, isError = false): void {
  noticeEl.classList.toggle("banner--error", isError);
  noticeEl.classList.toggle("show", Boolean(text));
  noticeEl.textContent = text ?? "";
}

function gameId(): string {
  return state.room?.game_id ?? state.selectedGame;
}
function myRole(snapshot: GameSnapshot): string | null {
  return snapshot.symbols?.[state.playerId ?? ""] ?? null;
}

// --- header / outcome -------------------------------------------------------
function roleText(): string {
  const s = state.snapshot;
  if (!s) return "—";
  if (gameId() === "snake" || gameId() === "racing") return "You";
  const role = myRole(s);
  return typeof role === "string" && role ? role : "you";
}

function turnText(snapshot: GameSnapshot): string {
  if (snapshot.finished) return "Game over";
  const gid = gameId();
  if (gid === "quiz") {
    return snapshot.current === state.playerId ? "Your turn" : "Waiting for opponent…";
  }
  if (gid === "chess") {
    return snapshot.turn === myRole(snapshot) ? "Your move" : "Opponent's move";
  }
  if (gid === "pong") return "↑ ↓ move your paddle";
  if (gid === "snake") {
    if (snapshot.phase === "starting") return `Starting in ${snapshot.countdown}s…`;
    return "↑ ↓ ← → steer your snake · eat food & survive";
  }
  if (gid === "racing") {
    if (snapshot.phase === "starting") return `Starting in ${snapshot.countdown}s…`;
    return "W/↑ accelerate · S/↓ brake · A/D steer";
  }
  return snapshot.whos_turn === state.playerId ? "Your turn" : "Opponent's turn";
}

function didWin(r: { winner: string | null; draw: boolean }): boolean {
  if (r.draw) return false;
  if (["chess", "pong", "snake", "racing"].includes(gameId())) return r.winner === state.playerId;
  // tic-tac-toe reports a symbol; quiz reports a player id
  return r.winner === myRole(state.snapshot ?? {});
}

function outcomeText(): string {
  const r = state.result;
  if (!r) return "";
  if (gameId() === "quiz") return ""; // quiz renderer draws its own result
  if (r.draw) return "Draw";
  if (r.reason === "forfeit" || r.reason === "abandoned")
    return r.winner === state.playerId ? "You win" : "You lose";
  return gameId() === "chess"
    ? didWin(r)
      ? "Checkmate — you win"
      : "Checkmate — you lose"
    : didWin(r)
      ? "You win"
      : "You lose";
}

// --- rendering --------------------------------------------------------------
function render(): void {
  statusEl.textContent = state.status;
  statusEl.classList.toggle("offline", !state.status.includes("connected"));

  // Don't allow lobby actions until we have a server-assigned identity, so an
  // early click can't be rejected with "must hello first".
  const bound = Boolean(state.playerId);
  ["find", "create", "list", "cancel", "join", "start", "leave-lobby"].forEach((id) => {
    const b = byId(id) as HTMLButtonElement | null;
    if (b) b.disabled = !bound;
  });

  if (state.screen !== "game" || gameId() !== "pong") lastPongDir = 0;
  if (state.screen !== "game" || gameId() !== "snake") lastSnakeDir = "";
  if (state.screen !== "game" || gameId() !== "racing") racingPressed.clear();

  const room = state.room;
  if (room) {
    lobbyCodeEl.textContent = room.id;
    roomWaitingEl.style.display = room.status === "waiting" ? "" : "none";
    roomMetaEl.textContent = ` · ${room.players.length} player(s) · ${GAME_NAMES[room.game_id] ?? room.game_id}`;
    const isHost = room.host_id === state.playerId;
    const startBtn = byId("start");
    const leaveLobbyBtn = byId("leave-lobby");
    if (startBtn) startBtn.style.display = isHost && room.status === "waiting" ? "" : "none";
    if (leaveLobbyBtn) leaveLobbyBtn.style.display = "";
  }
  roomCardEl.classList.toggle("show", Boolean(state.room) && state.screen === "lobby");

  if (state.screen === "game" && state.snapshot) {
    lobbyEl.style.display = "none";
    gameEl.style.display = "block";
    mySymEl.textContent = roleText();
    turnEl.textContent = turnText(state.snapshot);
    resultEl.textContent = outcomeText();
    resultEl.classList.remove("win", "lose", "draw");
    const r = state.result;
    if (r && gameId() !== "quiz") {
      resultEl.classList.add(r.draw ? "draw" : didWin(r) ? "win" : "lose");
    }
    // Show "Play again" once the game has ended; reflect the vote state.
    const rematchBtn = byId("rematch") as HTMLButtonElement | null;
    if (rematchBtn) {
      rematchBtn.style.display = state.result || state.snapshot.finished ? "" : "none";
      rematchBtn.textContent = state.rematchVoted ? "Waiting for others…" : "↻ Play again";
      rematchBtn.disabled = state.rematchVoted;
    }

    const renderer = GAME_RENDERERS[gameId()];
    const ctx: RenderCtx = {
      snapshot: state.snapshot,
      me: state.playerId,
      send: (action) => conn.send("game_action", { action }),
    };
    if (renderer) renderer(boardEl, ctx);
    else boardEl.textContent = "Game not supported";
  } else {
    gameEl.style.display = "none";
    lobbyEl.style.display = "block";
    renderRoomList();
    renderGamePicker();
  }
}

function renderGamePicker(): void {
  const wrap = byId("game-picker");
  if (!wrap) return;
  wrap.innerHTML = "";
  Object.entries(GAME_NAMES).forEach(([gid, name]) => {
    const btn = document.createElement("button");
    btn.className = "game-pick" + (state.selectedGame === gid ? " active" : "");
    btn.textContent = name;
    btn.addEventListener("click", () => {
      state.selectedGame = gid;
      render();
    });
    wrap.appendChild(btn);
  });
}

function renderRoomList(): void {
  roomListEl.innerHTML = "";
  if (!state.rooms.length) {
    roomListEl.innerHTML = '<div class="empty">No open rooms right now — create one!</div>';
    return;
  }
  state.rooms.forEach((room) => {
    const el = document.createElement("div");
    el.className = "room";
    const info = document.createElement("div");
    const name = document.createElement("div");
    name.className = "room__name";
    name.textContent = GAME_NAMES[room.game_id] ?? room.game_id;
    const meta = document.createElement("div");
    meta.className = "room__meta";
    meta.textContent = `${room.players.length} player(s) · ${room.id}`;
    info.append(name, meta);
    const cta = document.createElement("span");
    cta.className = "room__cta";
    cta.textContent = "Join";
    el.append(info, cta);
    el.addEventListener("click", () => conn.send("join_room", { room_id: room.id }));
    roomListEl.appendChild(el);
  });
}

// --- message reducer --------------------------------------------------------
function apply(message: Envelope): void {
  const p = message.payload;
  switch (message.type) {
    case "hello_ack":
      rejoinPending = false;
      state.playerId = p.player_id as string;
      write(STORAGE.playerId, state.playerId);
      setNotice(null);
      // Populate the lobby immediately instead of leaving it empty until the
      // user manually presses "Rooms".
      conn.send("list_rooms");
      break;
    case "room_created":
    case "room_joined":
      state.room = p.room as RoomInfo;
      setNotice(null);
      break;
    case "match_found":
      state.room = p.room as RoomInfo;
      flash("Match found!");
      break;
    case "room_update":
      state.room = p.room as RoomInfo;
      break;
    case "room_list":
      state.rooms = (p.rooms as RoomInfo[]) ?? [];
      break;
    case "room_left":
      // Leave: return to the lobby, drop all game/session state.
      state.room = null;
      state.snapshot = null;
      state.result = null;
      state.sessionId = null;
      state.screen = "lobby";
      clear(STORAGE.sessionId);
      setNotice(null);
      conn.send("list_rooms"); // refresh the lobby list now that we're back
      break;
    case "queue_ack":
      if (p.queued) flash("Looking for an opponent…");
      else flash("Left matchmaking");
      break;
    case "game_started": {
      state.sessionId = p.session_id as string;
      write(STORAGE.sessionId, state.sessionId);
      state.snapshot = p.state as GameSnapshot;
      state.result = null;
      state.screen = "game";
      state.rematchVoted = false; // a new game resets the rematch votes
      resetBoard(); // fresh tic-tac-toe animation cache
      resetChess(); // clear any stale piece selection
      setNotice(null);
      break;
    }
    case "state_update":
      rejoinPending = false; // a resync snapshot means rejoin succeeded
      state.snapshot = p.state as GameSnapshot;
      // A state_update always describes an in-progress game. This is the only
      // signal we get back on a successful rejoin (no room_joined/room_update
      // is sent), so without this the client stayed stuck on the lobby screen
      // after closing and reopening the browser mid-game.
      state.screen = "game";
      setNotice(null);
      break;
    case "game_over":
      state.snapshot = p.state as GameSnapshot;
      state.result = p.result as never;
      clear(STORAGE.sessionId);
      flash("Game over");
      break;
    case "peer_disconnected":
      setNotice("Your opponent disconnected — waiting…");
      break;
    case "peer_reconnected":
      setNotice("Your opponent reconnected");
      break;
    case "rematch_requested":
      setNotice(
        p.votes === p.total
          ? "All players agreed — starting rematch!"
          : `Rematch: ${p.votes}/${p.total} players ready`
      );
      break;
    case "error":
      if (rejoinPending) {
        // The stored session is stale (server restarted / game ended) — start
        // fresh with a new identity instead of staying unbound, and don't
        // surface an error we've already recovered from.
        rejoinPending = false;
        state.playerId = null;
        state.sessionId = null;
        clear(STORAGE.playerId);
        clear(STORAGE.sessionId);
        conn.send("hello");
        break;
      }
      setNotice(String(p.message ?? "Something went wrong"), true);
      break;
    default:
      break;
  }
}

// --- wire-up ----------------------------------------------------------------
conn.onStatus = (s: string) => {
  state.status = s;
  render();
};
conn.onMessage = (m: Envelope) => {
  apply(m);
  render();
};
conn.onOpen = () => {
  const savedPlayer = read<string>(STORAGE.playerId);
  const savedSession = read<string>(STORAGE.sessionId);
  if (savedPlayer && savedSession) {
    state.playerId = savedPlayer;
    state.sessionId = savedSession;
    rejoinPending = true;
    conn.send("rejoin", { player_id: savedPlayer, session_id: savedSession });
  } else {
    rejoinPending = false;
    conn.send("hello");
  }
};

function onClick(id: string, fn: () => void): void {
  byId(id)?.addEventListener("click", fn);
}

onClick("find", () => {
  if (QUICK_MATCH_GAMES.includes(state.selectedGame)) {
    conn.send("find_match", { game_id: state.selectedGame });
  } else {
    flash("Quick match is only for 2-player games");
  }
});
onClick("create", () => conn.send("create_room", { game_id: state.selectedGame }));
onClick("list", () => conn.send("list_rooms"));
onClick("cancel", () => conn.send("cancel_match"));
onClick("start", () => conn.send("start_game"));
onClick("leave", () => conn.send("leave_room"));
onClick("leave-lobby", () => conn.send("leave_room"));
onClick("rematch", () => {
  state.rematchVoted = true;
  conn.send("rematch");
});
onClick("join", () => {
  const code = joinCodeInput.value.trim();
  if (code) conn.send("join_room", { room_id: code });
  else flash("Enter a room code first");
});
joinCodeInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") byId("join")?.click();
});
onClick("copy-room", async () => {
  if (!state.room) return;
  try {
    await navigator.clipboard.writeText(state.room.id);
    flash("Room code copied");
  } catch {
    flash(`Room code: ${state.room.id}`);
  }
});

// --- realtime input (Pong) -------------------------------------------------
// While in a live pong game, the arrow keys steer your paddle. We send the
// held direction on keydown and clear it on keyup; the server applies it.
function inPong(): boolean {
  return (
    gameId() === "pong" &&
    state.screen === "game" &&
    !!state.snapshot &&
    !state.snapshot.finished &&
    !!state.snapshot.symbols?.[state.playerId ?? ""]
  );
}

function inSnake(): boolean {
  return (
    gameId() === "snake" &&
    state.screen === "game" &&
    !!state.snapshot &&
    !state.snapshot.finished
  );
}

function inRacing(): boolean {
  return (
    gameId() === "racing" &&
    state.screen === "game" &&
    !!state.snapshot &&
    !state.snapshot.finished
  );
}

// --- racing keyboard input ----------------------------------------------
const racingPressed = new Set<string>();
function setRacingHeld(): void {
  const accel = racingPressed.has("w") || racingPressed.has("arrowup");
  const brake = racingPressed.has("s") || racingPressed.has("arrowdown");
  const left = racingPressed.has("a") || racingPressed.has("arrowleft");
  const right = racingPressed.has("d") || racingPressed.has("arrowright");
  const cur = { accel, brake, left, right };
  const prev = racingHeldSnapshot;
  if (cur.accel === prev.accel && cur.brake === prev.brake && cur.left === prev.left && cur.right === prev.right) return;
  racingHeldSnapshot = cur;
  conn.send("game_action", { action: cur });
}
type RacingHeld = { accel: boolean; brake: boolean; left: boolean; right: boolean };
let racingHeldSnapshot: RacingHeld = { accel: false, brake: false, left: false, right: false };

function setPongDir(dir: number): void {
  if (dir === lastPongDir) return; // unchanged → don't resend
  lastPongDir = dir;
  conn.send("game_action", { action: { dir } });
}

const SNAKE_DIRS: Record<string, string> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
};
let lastSnakeDir = "";
function setSnakeDir(dir: string): void {
  if (dir === lastSnakeDir) return; // only send on change
  lastSnakeDir = dir;
  conn.send("game_action", { action: { dir } });
}

window.addEventListener("keydown", (e) => {
  if (inPong()) {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setPongDir(-1);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setPongDir(1);
    }
    return;
  }
  if (inSnake()) {
    const d = SNAKE_DIRS[e.key];
    if (d) {
      e.preventDefault();
      setSnakeDir(d);
    }
    return;
  }
  if (inRacing()) {
    const k = e.key.toLowerCase();
    if ("wasd".includes(k) || e.key.startsWith("Arrow")) {
      e.preventDefault();
      racingPressed.add(k);
      setRacingHeld();
    }
  }
});
window.addEventListener("keyup", (e) => {
  if (inPong() && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
    setPongDir(0);
    return;
  }
  if (inRacing()) {
    const k = e.key.toLowerCase();
    if (racingPressed.has(k)) {
      racingPressed.delete(k);
      setRacingHeld();
    }
  }
});

subscribe(render);
render();
conn.connect();
