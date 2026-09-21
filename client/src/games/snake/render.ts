/// Snake Battle canvas renderer. Draws the grid, food and every snake from each
/// server snapshot (pushed ~8x/sec), plus a colour legend and, during the
/// countdown, which snake is yours. No game logic lives here.

import type { GameSnapshot } from "../../protocol";
import { dim, pill, roundRect } from "../canvas";
import type { RenderCtx, Role } from "../types";

/// Indexed by the snake's `color` from the server (snapshot.symbols).
export const SNAKE_COLORS = [
  { name: "Blue", hex: "#2c7a8c" },
  { name: "Red", hex: "#c1502f" },
  { name: "Yellow", hex: "#d79f3d" },
  { name: "Green", hex: "#4f9153" },
];

function colorOf(index: number) {
  return SNAKE_COLORS[index % SNAKE_COLORS.length];
}

export function snakeRole(s: GameSnapshot, me: string | null): Role | null {
  const idx = s.symbols?.[me ?? ""];
  if (typeof idx !== "number") return null;
  const c = colorOf(idx);
  return { label: c.name, color: c.hex };
}

interface SnakeView {
  player_id: string;
  color: number;
  alive: boolean;
  score: number;
  body: number[][];
}

let wrap: HTMLElement | null = null;
let canvas: HTMLCanvasElement | null = null;
let legend: HTMLElement | null = null;

export function renderSnake(container: HTMLElement, ctx: RenderCtx): void {
  const s = ctx.snapshot;
  if (!wrap || wrap.parentElement !== container || !canvas || !legend) {
    container.innerHTML = "";
    wrap = document.createElement("div");
    wrap.className = "snake-wrap";
    legend = document.createElement("div");
    legend.className = "snake-legend";
    canvas = document.createElement("canvas");
    canvas.className = "snake-canvas";
    canvas.width = 560;
    canvas.height = 560;
    wrap.append(legend, canvas);
    container.appendChild(wrap);
  }
  const g = canvas.getContext("2d");
  if (!g) return;

  const snakes = s.snakes as SnakeView[];
  const mine = snakes.find((k) => k.player_id === ctx.me) ?? null;
  drawLegend(legend, snakes, ctx.me);

  const W = s.board.w as number;
  const H = s.board.h as number;
  const size = canvas.width;
  const margin = 8;
  const cell = (size - 2 * margin) / W;

  g.fillStyle = "#16302a";
  g.fillRect(0, 0, size, size);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      g.fillStyle = (x + y) % 2 === 0 ? "#1b3c33" : "#18352d";
      g.fillRect(margin + x * cell, margin + y * cell, cell, cell);
    }
  }
  g.strokeStyle = "rgba(247,240,220,0.15)";
  g.strokeRect(margin, margin, W * cell, H * cell);

  // food: cream dots, so it never looks like a (yellow) snake
  (s.food as number[][]).forEach((f) => {
    g.fillStyle = "#f7f0dc";
    g.beginPath();
    g.arc(margin + (f[0] + 0.5) * cell, margin + (f[1] + 0.5) * cell, cell * 0.3, 0, Math.PI * 2);
    g.fill();
  });

  snakes.forEach((snk) => {
    const color = colorOf(snk.color).hex;
    g.globalAlpha = snk.alive ? 1 : 0.3;
    snk.body.forEach((xy, i) => {
      g.fillStyle = i === 0 ? lighten(color) : color;
      const pad = cell * 0.08;
      roundRect(g, margin + xy[0] * cell + pad, margin + xy[1] * cell + pad, cell - pad * 2, cell - pad * 2, cell * 0.28);
      g.fill();
    });
    g.globalAlpha = 1;
  });

  // your head gets a white frame all game long
  if (mine && mine.alive) {
    const h = mine.body[0];
    g.strokeStyle = "#fff";
    g.lineWidth = 3;
    g.strokeRect(margin + h[0] * cell + cell * 0.1, margin + h[1] * cell + cell * 0.1, cell * 0.8, cell * 0.8);
  }

  if (s.finished) {
    dim(g, size, 0.55);
    g.fillStyle = "#f7f0dc";
    g.textAlign = "center";
    g.textBaseline = "alphabetic";
    g.font = "800 34px system-ui, sans-serif";
    g.fillText(s.winner === ctx.me ? "You win!" : "Game over", size / 2, size / 2 - 10);
    g.font = "600 18px system-ui, sans-serif";
    g.fillText("Press Play again for a rematch", size / 2, size / 2 + 22);
  } else if (s.phase === "starting") {
    drawCountdown(g, s, size, margin, cell, mine);
  }
}

function drawCountdown(g: CanvasRenderingContext2D, s: GameSnapshot, size: number, margin: number, cell: number, mine: SnakeView | null): void {
  dim(g, size);
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillStyle = "#f7f0dc";
  g.font = "700 30px system-ui, sans-serif";
  g.fillText("Get ready", size / 2, 55);
  g.font = "800 110px system-ui, sans-serif";
  g.fillText(String(s.countdown as number), size / 2, 140);

  if (mine) {
    const c = colorOf(mine.color);
    pill(g, size / 2, 425, `You are ${c.name.toUpperCase()}`, c.hex, 32);

    // ring + label on your own snake, drawn above the dimming layer
    const [hx, hy] = mine.body[0];
    const cx = margin + (hx + 0.5) * cell;
    const cy = margin + (hy + 0.5) * cell;
    g.strokeStyle = "#fff";
    g.lineWidth = 4;
    g.beginPath();
    g.arc(cx, cy, cell * 1.1, 0, Math.PI * 2);
    g.stroke();
    g.fillStyle = c.hex;
    g.beginPath();
    g.arc(cx, cy, cell * 0.45, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = "#fff";
    g.font = "800 18px system-ui, sans-serif";
    g.fillText("YOU", cx, cy + (cy < size / 2 ? cell * 1.9 : -cell * 1.9));
  }

  g.fillStyle = "rgba(247,240,220,0.85)";
  g.font = "600 21px system-ui, sans-serif";
  g.fillText("Swipe on the board to steer (or use the arrow keys)", size / 2, 500);
}

function drawLegend(el: HTMLElement, snakes: SnakeView[], me: string | null): void {
  el.replaceChildren(
    ...snakes.map((snk) => {
      const c = colorOf(snk.color);
      const chip = document.createElement("span");
      chip.className = "snake-chip" + (snk.player_id === me ? " me" : "") + (snk.alive ? "" : " dead");
      const dot = document.createElement("i");
      dot.style.background = c.hex;
      const text = document.createElement("span");
      text.textContent = `${c.name}${snk.player_id === me ? " (you)" : ""} · ${snk.score}${snk.alive ? "" : " ✕"}`;
      chip.append(dot, text);
      return chip;
    }),
  );
}

function lighten(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  const ch = (shift: number) => Math.min(255, ((n >> shift) & 0xff) + 45);
  return `rgb(${ch(16)},${ch(8)},${ch(0)})`;
}
