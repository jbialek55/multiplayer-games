import { WsConnection } from "./net/ws";
import { currentGameId, state } from "./state";
import { STORAGE, type Envelope, type RoomInfo, type GameSnapshot } from "./protocol";
import { GAME_RENDERERS, GAME_NAMES, QUICK_MATCH_GAMES, roleOf, type RenderCtx, type Role } from "./games";
import { resetChess } from "./games/chess/render";
import { resetBoard } from "./games/tictactoe/render";
import { resetQuiz } from "./games/quiz/render";
import { initInput, resetInput, setTouchMode } from "./input";
import { renderHowTo } from "./howto";

const conn = new WsConnection();

// True between sending a `rejoin` on connect and knowing it worked. If the
// server rejects it (stale session after a restart/ended game), we fall back to
// a fresh `hello` so the connection is never left unbound.
let rejoinPending = false;

// --- elements ---------------------------------------------------------------
function byId(id: string): HTMLElement | null {
  return document.getElementById(id);
}

const statusEl = byId("status") as HTMLDivElement;
const noticeEl = byId("notice") as HTMLDivElement;
const lobbyEl = byId("lobby") as HTMLElement;
const gameEl = byId("game") as HTMLElement;
const boardEl = byId("board") as HTMLDivElement;
const gameHowToEl = byId("game-howto") as HTMLDetailsElement;
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

const gameId = currentGameId;
function myRole(snapshot: GameSnapshot): string | null {
  return snapshot.symbols?.[state.playerId ?? ""] ?? null;
}

// --- header / outcome -------------------------------------------------------
function roleText(): Role {
  const s = state.snapshot;
  if (!s) return { label: "—" };
  const role = roleOf(gameId(), s, state.playerId);
  if (role) return role;
  const symbol = myRole(s);
  return { label: typeof symbol === "string" && symbol ? symbol : "you" };
}

function turnText(snapshot: GameSnapshot): string {
  const gid = gameId();
  if (gid === "quiz") return ""; // the quiz renderer draws its own turn line
  if (snapshot.finished) return "Game over";
  if (gid === "chess") {
    return snapshot.turn === myRole(snapshot) ? "Your move" : "Opponent's move";
  }
  if (gid === "pong") {
    return snapshot.phase === "starting" ? "Get ready…" : "Drag your finger up and down to move your paddle";
  }
  if (gid === "snake") {
    return snapshot.phase === "starting" ? "Get ready…" : "Swipe on the board to steer · eat food & survive";
  }
  return snapshot.whos_turn === state.playerId ? "Your turn" : "Opponent's turn";
}

function didWin(r: { winner: string | null; draw: boolean }): boolean {
  if (r.draw) return false;
  if (["chess", "pong", "snake"].includes(gameId())) return r.winner === state.playerId;
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
    const role = roleText();
    mySymEl.textContent = role.label;
    mySymEl.classList.toggle("has-dot", Boolean(role.color));
    if (role.color) mySymEl.style.setProperty("--dot", role.color);
    setTouchMode(boardEl, gameId());
    renderHowTo(gameHowToEl, gameId(), state.snapshot.phase === "starting");
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
      resetInput();
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
      resetQuiz(); // don't replay the last game's answer reveal
      resetInput(); // a new paddle/snake: the first press must be sent
      gameHowToEl.dataset.game = ""; // show the how-to open again for the new game
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
// The logo takes you back to the main screen. That means leaving the room, so
// ask first if a game is still running.
onClick("brand", () => {
  if (state.screen !== "game") return;
  const running = state.snapshot !== null && !state.snapshot.finished;
  if (running && !window.confirm("Leave this game and go back to the main screen?")) return;
  conn.send("leave_room");
});
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

// --- realtime input (Pong / Snake): keyboard, touch pads, swipes ------------
initInput((action) => conn.send("game_action", { action }), boardEl);

render();
conn.connect();
