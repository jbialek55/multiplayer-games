/// Pong canvas renderer. Draws on a requestAnimationFrame loop and linearly
/// interpolates the ball/paddles between server snapshots so motion is smooth
/// even when updates arrive unevenly. During the server's 3 s countdown it
/// tells the player which side they are on. The loop stops when the canvas is
/// no longer visible.

import type { GameSnapshot } from "../../protocol";
import { dim, pill, roundRect } from "../canvas";
import type { RenderCtx, Role } from "../types";

const SIDES = {
  L: { name: "LEFT", label: "Left", color: "#2c7a8c" },
  R: { name: "RIGHT", label: "Right", color: "#c1502f" },
} as const;
type Side = keyof typeof SIDES;

function mySide(s: GameSnapshot, me: string | null): Side | null {
  const v = s.symbols?.[me ?? ""];
  return v === "L" || v === "R" ? v : null;
}

export function pongRole(s: GameSnapshot, me: string | null): Role | null {
  const side = mySide(s, me);
  return side ? { label: SIDES[side].label, color: SIDES[side].color } : null;
}

const MARGIN = 30; // canvas px between the edge and the playing field

let canvas: HTMLCanvasElement | null = null;
let me: string | null = null;
let lastSnap: GameSnapshot | null = null;
let rafId: number | null = null;

// What is actually drawn. It chases the latest server snapshot with an
// exponential ease instead of jumping to it, so uneven packet arrival (the
// server sends 60 snapshots/s) never shows up as stutter. The old code tried to
// interpolate between snapshots but its progress was always already 1, i.e. it
// jumped to every new snapshot -- smooth only on a perfectly even connection.
interface Shown {
  ballX: number;
  ballY: number;
  padL: number;
  padR: number;
  ts: number;
}
let shown: Shown | null = null;
const SMOOTH_TAU_MS = 35; // time constant of the ease
const SNAP_DIST = 12; // field units: a bigger jump (serve, new point) is not eased

export function resetPong(): void {
  shown = null;
  lastSnap = null;
}

export function renderPong(container: HTMLElement, ctx: RenderCtx): void {
  me = ctx.me;
  if (!canvas || canvas.parentElement !== container) {
    container.innerHTML = "";
    canvas = document.createElement("canvas");
    canvas.className = "pong-canvas";
    canvas.width = 620;
    canvas.height = 620;
    container.appendChild(canvas);
    shown = null;
  }
  lastSnap = ctx.snapshot;
  if (!shown || ctx.snapshot.phase === "starting" || ctx.snapshot.finished) shown = target(ctx.snapshot);
  if (rafId == null) rafId = requestAnimationFrame(loop);
  else if (ctx.snapshot.phase === "starting" || ctx.snapshot.finished) draw(canvas, view());
}

function target(s: GameSnapshot): Shown {
  return {
    ballX: s.ball.x as number,
    ballY: s.ball.y as number,
    padL: s.paddles.l as number,
    padR: s.paddles.r as number,
    ts: performance.now(),
  };
}

/// Field y (0..100) under a viewport y coordinate, or null when there is no
/// board. Used to turn a finger position into a paddle target.
export function fieldY(clientY: number): number | null {
  if (!canvas || !lastSnap) return null;
  const rect = canvas.getBoundingClientRect();
  if (!rect.height) return null;
  const px = ((clientY - rect.top) / rect.height) * canvas.width;
  const scale = (canvas.width - 2 * MARGIN) / (lastSnap.field.w as number);
  return (px - MARGIN) / scale;
}

/// Centre y of your own paddle in the latest snapshot.
export function myPaddleY(): number | null {
  const side = lastSnap ? mySide(lastSnap, me) : null;
  return lastSnap && side ? (lastSnap.paddles[side === "L" ? "l" : "r"] as number) : null;
}

function loop(): void {
  // Stop when the board is gone or hidden (lobby); renderPong restarts it.
  if (!canvas || !lastSnap || !canvas.isConnected || canvas.offsetParent === null) {
    rafId = null;
    return;
  }
  draw(canvas, view());
  rafId = requestAnimationFrame(loop);
}

/// Advance the eased position towards the latest snapshot and return a
/// snapshot to draw.
function view(): GameSnapshot {
  const t = target(lastSnap!);
  if (!shown) shown = t;
  const dt = Math.min(100, Math.max(0, t.ts - shown.ts));
  const k = 1 - Math.exp(-dt / SMOOTH_TAU_MS);
  const far = Math.hypot(t.ballX - shown.ballX, t.ballY - shown.ballY) > SNAP_DIST;
  const f = far ? 1 : k;
  shown = {
    ballX: lerp(shown.ballX, t.ballX, f),
    ballY: lerp(shown.ballY, t.ballY, f),
    padL: lerp(shown.padL, t.padL, k),
    padR: lerp(shown.padR, t.padR, k),
    ts: t.ts,
  };
  return {
    ...lastSnap!,
    ball: { x: shown.ballX, y: shown.ballY },
    paddles: { l: shown.padL, r: shown.padR },
  };
}

function lerp(x: number, y: number, p: number): number {
  return x + (y - x) * p;
}

function draw(canvas: HTMLCanvasElement, s: GameSnapshot): void {
  const g = canvas.getContext("2d");
  if (!g) return;

  const W = s.field.w as number;
  const padH = s.field.pad_h as number;
  const padW = s.field.pad_w as number;
  const ballR = s.field.ball_r as number;

  const size = canvas.width;
  const margin = MARGIN;
  const scale = (size - 2 * margin) / W;
  const padWpx = Math.max(4, padW * scale);
  const padHpx = padH * scale;
  const ballPx = Math.max(4, ballR * scale);
  const side = mySide(s, me);
  const starting = s.phase === "starting" && !s.finished;

  g.fillStyle = "#16302a";
  g.fillRect(0, 0, size, size);

  g.strokeStyle = "rgba(247,240,220,0.25)";
  g.lineWidth = 2;
  g.strokeRect(margin, margin, size - 2 * margin, size - 2 * margin);

  g.strokeStyle = "rgba(247,240,220,0.2)";
  g.setLineDash([8, 10]);
  g.beginPath();
  g.moveTo(size / 2, margin);
  g.lineTo(size / 2, size - margin);
  g.stroke();
  g.setLineDash([]);

  // paddles; yours gets a white frame
  const paddles: Array<[Side, number, number]> = [
    ["L", margin, s.paddles.l as number],
    ["R", size - margin - padWpx, s.paddles.r as number],
  ];
  for (const [id, x, centre] of paddles) {
    g.fillStyle = SIDES[id].color;
    roundRect(g, x, margin + centre * scale - padHpx / 2, padWpx, padHpx, Math.min(padWpx, padHpx) / 3);
    g.fill();
    if (id === side) {
      g.strokeStyle = "#fff";
      g.lineWidth = 3;
      g.stroke();
    }
  }

  g.fillStyle = "#f7f0dc";
  g.beginPath();
  g.arc(margin + (s.ball.x as number) * scale, margin + (s.ball.y as number) * scale, ballPx, 0, Math.PI * 2);
  g.fill();

  g.fillStyle = "rgba(247,240,220,0.9)";
  g.font = "700 42px system-ui, sans-serif";
  g.textAlign = "center";
  g.textBaseline = "top";
  g.fillText(String(s.scores.l as number), size / 2 - 56, 12);
  g.fillText(String(s.scores.r as number), size / 2 + 56, 12);

  if (side) {
    g.fillStyle = "#fff";
    g.font = "800 14px system-ui, sans-serif";
    g.fillText("YOU", size / 2 + (side === "L" ? -56 : 56), 60);
  }

  g.fillStyle = "rgba(247,240,220,0.35)";
  g.font = "600 13px system-ui, sans-serif";
  g.fillText(`first to ${s.win_score as number}`, size / 2, size - margin + 8);

  if (starting) drawCountdown(g, s, size, side, margin + padWpx);
}

function drawCountdown(g: CanvasRenderingContext2D, s: GameSnapshot, size: number, side: Side | null, padEdge: number): void {
  dim(g, size, 0.45);
  g.fillStyle = "#f7f0dc";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.font = "800 150px system-ui, sans-serif";
  g.fillText(String(s.countdown as number), size / 2, size / 2 - 50);

  if (!side) return;
  pill(g, size / 2, size / 2 + 80, `You play ${SIDES[side].name}`, SIDES[side].color, 34);

  // an arrow pointing at your own paddle (short, so it stays clear of the ball)
  g.fillStyle = "#fff";
  g.font = "800 26px system-ui, sans-serif";
  g.textBaseline = "middle";
  if (side === "L") {
    g.textAlign = "left";
    g.fillText("◀ YOU", padEdge + 12, size / 2);
  } else {
    g.textAlign = "right";
    g.fillText("YOU ▶", size - padEdge - 12, size / 2);
  }

  g.textAlign = "center";
  g.fillStyle = "rgba(247,240,220,0.85)";
  g.font = "600 22px system-ui, sans-serif";
  g.fillText("Drag your finger up and down to move (or ↑ ↓ keys)", size / 2, size / 2 + 150);
}
