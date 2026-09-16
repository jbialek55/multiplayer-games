/// Snake Battle canvas renderer. Draws the grid, food, every snake, scores and
/// the current phase/countdown from each server snapshot (pushed ~8x/sec).
/// No game logic lives here — it only reflects the authoritative state.

import type { GameSnapshot } from "../../protocol";

const PALETTE = ["#2c7a8c", "#c1502f", "#d79f3d", "#4f9153"];

interface Ctx {
  snapshot: GameSnapshot;
  me: string | null;
  send: (action: Record<string, unknown>) => void;
}

let canvas: HTMLCanvasElement | null = null;

export function renderSnake(container: HTMLElement, ctx: Ctx): void {
  const s = ctx.snapshot;
  if (!canvas || canvas.parentElement !== container) {
    container.innerHTML = "";
    canvas = document.createElement("canvas");
    canvas.className = "snake-canvas";
    canvas.width = 560;
    canvas.height = 560;
    container.appendChild(canvas);
  }
  const g = canvas.getContext("2d");
  if (!g) return;

  const W = s.board.w as number;
  const H = s.board.h as number;
  const size = canvas.width;
  const margin = 8;
  const cell = (size - 2 * margin) / W;

  // checkerboard backdrop
  g.fillStyle = "#16302a";
  g.fillRect(0, 0, size, size);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      g.fillStyle = (x + y) % 2 === 0 ? "#1b3c33" : "#18352d";
      g.fillRect(margin + x * cell, margin + y * cell, cell, cell);
    }
  }

  // grid outline
  g.strokeStyle = "rgba(247,240,220,0.15)";
  g.strokeRect(margin, margin, W * cell, H * cell);

  // food
  s.food.forEach((f: number[]) => {
    g.fillStyle = "#d98f2b";
    g.beginPath();
    g.arc(margin + (f[0] + 0.5) * cell, margin + (f[1] + 0.5) * cell, cell * 0.35, 0, Math.PI * 2);
    g.fill();
  });

  // snakes
  const snakes = s.snakes as Array<{ player_id: string; color: number; alive: boolean; score: number; body: number[][] }>;
  snakes.forEach((snk) => {
    const color = PALETTE[snk.color % PALETTE.length];
    snk.body.forEach((cellXY, i) => {
      const isHead = i === 0;
      g.fillStyle = isHead ? lighten(color) : color;
      const pad = cell * 0.08;
      roundRect(
        g,
        margin + cellXY[0] * cell + pad,
        margin + cellXY[1] * cell + pad,
        cell - pad * 2,
        cell - pad * 2,
        cell * 0.28,
      );
      g.fill();
      if (!snk.alive) g.fillStyle = "rgba(0,0,0,0.55)";
    });
    // alive marker for the player's own snake
    if (snk.player_id === ctx.me && snk.alive) {
      const h = snk.body[0];
      g.strokeStyle = "#fff";
      g.lineWidth = 2;
      g.strokeRect(margin + h[0] * cell + cell * 0.15, margin + h[1] * cell + cell * 0.15, cell * 0.7, cell * 0.7);
    }
  });

  // scores row
  g.fillStyle = "rgba(244,240,232,0.9)";
  g.font = "700 16px system-ui, sans-serif";
  g.textAlign = "left";
  let sx = margin + 4;
  snakes.forEach((snk, i) => {
    g.fillStyle = PALETTE[snk.color % PALETTE.length];
    g.fillText(`${i + 1}: ${snk.score}`, sx, size - margin - 8);
    sx += 56;
  });

  // phase overlay
  if (s.phase === "starting") {
    g.fillStyle = "rgba(0,0,0,0.55)";
    g.fillRect(0, 0, size, size);
    g.fillStyle = "#f7f0dc";
    g.font = "700 30px system-ui, sans-serif";
    g.textAlign = "center";
    g.fillText(`Get ready — ${s.countdown}s`, size / 2, size / 2 - 10);
  } else if (s.phase === "finished") {
    g.fillStyle = "rgba(0,0,0,0.55)";
    g.fillRect(0, 0, size, size);
    g.fillStyle = "#f7f0dc";
    g.font = "800 34px system-ui, sans-serif";
    g.textAlign = "center";
    const won = s.winner === ctx.me;
    g.fillText(won ? "You win!" : "Game over", size / 2, size / 2 - 10);
    g.font = "600 18px system-ui, sans-serif";
    g.fillText("Press Play again for a rematch", size / 2, size / 2 + 22);
  }
}

function lighten(hex: string): string {
  // brighten a hex color for the snake head
  const n = parseInt(hex.slice(1), 16);
  const r = Math.min(255, ((n >> 16) & 0xff) + 45);
  const gsc = Math.min(255, ((n >> 8) & 0xff) + 45);
  const b = Math.min(255, (n & 0xff) + 45);
  return `rgb(${r},${gsc},${b})`;
}

function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
}
