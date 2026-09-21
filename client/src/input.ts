/// Realtime input for Pong and Snake Battle.
///
///  - Pong: drag a finger (or the mouse) up/down anywhere on the board and your
///    paddle follows, moving by the same amount you drag. Arrow keys work too.
///  - Snake: swipe on the board in the direction you want to go. Arrow keys too.
///
/// Keys and swipes only talk to the server when the direction changes; finger
/// drags are throttled, so neither can flood the connection.

import { fieldY, myPaddleY } from "./games/pong/render";
import { currentGameId, state } from "./state";

type Send = (action: Record<string, unknown>) => void;

const SWIPE_PX = 24; // finger travel that counts as a swipe
const TARGET_INTERVAL_MS = 60; // <= ~16 drag updates/s, under the server's rate limit
const SNAKE_KEYS: Record<string, string> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
};

let send: Send = () => {};
let lastPong = 0;
let lastSnake = "";

// pending finger-drag update for the paddle
let pendingTarget: number | null = null;
let lastTarget: number | null = null;
let lastSentAt = 0;
let flushTimer: number | undefined;

/// Is the local player in a live game of `game` right now?
function live(game: "pong" | "snake"): boolean {
  const s = state.snapshot;
  if (state.screen !== "game" || currentGameId() !== game || !s || s.finished) return false;
  return game === "snake" || Boolean(s.symbols?.[state.playerId ?? ""]);
}

function pongDir(dir: number): void {
  if (dir === lastPong) return;
  lastPong = dir;
  lastTarget = null; // the keyboard cancels any finger target on the server
  send({ dir });
}

function snakeDir(dir: string): void {
  if (dir === lastSnake) return;
  lastSnake = dir;
  send({ dir });
}

function flushTarget(): void {
  flushTimer = undefined;
  if (pendingTarget === null) return;
  const target = Math.round(pendingTarget * 10) / 10;
  pendingTarget = null;
  if (target === lastTarget) return;
  lastTarget = target;
  lastSentAt = performance.now();
  send({ target });
}

/// Ask the server to move the paddle to `y` (field units), at most every 60 ms.
function paddleTarget(y: number): void {
  pendingTarget = y;
  const wait = lastSentAt + TARGET_INTERVAL_MS - performance.now();
  if (wait <= 0) flushTarget();
  else if (flushTimer === undefined) flushTimer = window.setTimeout(flushTarget, wait);
}

/// Forget what we last sent. Call when a game starts or ends: a new game has a
/// fresh paddle/snake, so the first move must always go through.
export function resetInput(): void {
  lastPong = 0;
  lastSnake = "";
  lastTarget = null;
  pendingTarget = null;
  window.clearTimeout(flushTimer);
  flushTimer = undefined;
}

/// While a finger game is on screen the board must not scroll or zoom.
export function setTouchMode(board: HTMLElement, game: string): void {
  board.style.touchAction = game === "pong" || game === "snake" ? "none" : "";
}

export function initInput(sendAction: Send, board: HTMLElement): void {
  send = sendAction;

  window.addEventListener("keydown", (e) => {
    if (live("pong") && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
      e.preventDefault();
      pongDir(e.key === "ArrowUp" ? -1 : 1);
    } else if (live("snake") && SNAKE_KEYS[e.key]) {
      e.preventDefault();
      snakeDir(SNAKE_KEYS[e.key]);
    }
  });
  window.addEventListener("keyup", (e) => {
    if (live("pong") && (e.key === "ArrowUp" || e.key === "ArrowDown")) pongDir(0);
  });

  // One finger at a time. Pong: the paddle moves as far as the finger does
  // (relative drag, so your finger never hides the ball and the paddle never
  // jumps). Snake: travel is measured from the last turn, so one continuous
  // drag can chain several turns.
  let pong: { id: number; fingerY: number; paddleY: number } | null = null;
  let snake: { id: number; x: number; y: number } | null = null;

  board.addEventListener("pointerdown", (e) => {
    if (live("pong")) {
      const y = fieldY(e.clientY);
      const paddleY = myPaddleY();
      if (y === null || paddleY === null) return;
      pong = { id: e.pointerId, fingerY: y, paddleY };
    } else if (live("snake")) {
      snake = { id: e.pointerId, x: e.clientX, y: e.clientY };
    } else {
      return;
    }
    board.setPointerCapture(e.pointerId); // keep tracking if the finger leaves the board
    e.preventDefault();
  });

  board.addEventListener("pointermove", (e) => {
    if (pong && e.pointerId === pong.id && live("pong")) {
      const y = fieldY(e.clientY);
      if (y !== null) paddleTarget(pong.paddleY + (y - pong.fingerY));
    } else if (snake && e.pointerId === snake.id && live("snake")) {
      const dx = e.clientX - snake.x;
      const dy = e.clientY - snake.y;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < SWIPE_PX) return;
      snakeDir(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up");
      snake = { id: e.pointerId, x: e.clientX, y: e.clientY };
    }
  });

  const release = (e: PointerEvent) => {
    if (pong && e.pointerId === pong.id) {
      pong = null;
      flushTarget(); // put the paddle exactly where the finger stopped
    }
    if (snake && e.pointerId === snake.id) snake = null;
  };
  board.addEventListener("pointerup", release);
  board.addEventListener("pointercancel", release);
  board.addEventListener("contextmenu", (e) => e.preventDefault()); // long-press menu
}
