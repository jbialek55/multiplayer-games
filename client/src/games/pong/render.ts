/// Pong canvas renderer. Draws on a requestAnimationFrame loop and linearly
/// interpolates the ball/paddles between server snapshots so motion is smooth
/// even when updates arrive unevenly. The loop stops when the board is replaced.

import type { GameSnapshot } from "../../protocol";

interface Ctx {
  snapshot: GameSnapshot;
  me: string | null;
  send: (action: Record<string, unknown>) => void;
}

let canvas: HTMLCanvasElement | null = null;
let prevSnap: GameSnapshot | null = null;
let lastSnap: GameSnapshot | null = null;
let prevTs = 0;
let lastTs = 0;
let rafId: number | null = null;

export function renderPong(container: HTMLElement, ctx: Ctx): void {
  if (!canvas || canvas.parentElement !== container) {
    container.innerHTML = "";
    canvas = document.createElement("canvas");
    canvas.className = "pong-canvas";
    canvas.width = 620;
    canvas.height = 620;
    container.appendChild(canvas);
  }
  // shift history for interpolation
  if (lastSnap) {
    prevSnap = lastSnap;
    prevTs = lastTs;
  }
  lastSnap = ctx.snapshot;
  lastTs = performance.now();

  draw(canvas, ctx.snapshot);

  if (rafId == null) {
    rafId = requestAnimationFrame(function tick() {
      rafId = requestAnimationFrame(tick);
      if (!canvas || canvas.parentElement !== container) {
        rafId = null;
        return; // game switched away
      }
      if (!lastSnap) return;
      draw(canvas, interpolate());
    });
  }
}

function interpolate(): GameSnapshot {
  if (!prevSnap || prevTs >= lastTs) return lastSnap!;
  const p = Math.min(1, Math.max(0, (performance.now() - prevTs) / (lastTs - prevTs)));
  const a = prevSnap;
  const b = lastSnap!;
  return {
    ...b,
    ball: { x: lerp(a.ball.x, b.ball.x, p), y: lerp(a.ball.y, b.ball.y, p) },
    paddles: { l: lerp(a.paddles.l, b.paddles.l, p), r: lerp(a.paddles.r, b.paddles.r, p) },
  };
}

function lerp(x: number, y: number, p: number): number {
  return x + (y - x) * p;
}

function draw(canvas: HTMLCanvasElement, s: GameSnapshot): void {
  const g = canvas.getContext("2d");
  if (!g) return;

  const W = s.field.w as number;
  const H = s.field.h as number;
  const padH = s.field.pad_h as number;
  const padW = s.field.pad_w as number;
  const ballR = s.field.ball_r as number;

  const size = canvas.width;
  const margin = 30;
  const scale = (size - 2 * margin) / W;
  const padWpx = Math.max(4, padW * scale);
  const padHpx = padH * scale;
  const ballPx = Math.max(4, ballR * scale);
  const lp = s.paddles.l as number;
  const rp = s.paddles.r as number;

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

  g.fillStyle = "#2c7a8c";
  roundRect(g, margin, margin + lp * scale - padHpx / 2, padWpx, padHpx);
  g.fill();
  g.fillStyle = "#c1502f";
  roundRect(g, size - margin - padWpx, margin + rp * scale - padHpx / 2, padWpx, padHpx);
  g.fill();

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

  g.fillStyle = "rgba(247,240,220,0.35)";
  g.font = "600 13px system-ui, sans-serif";
  g.fillText(`first to ${s.win_score as number}`, size / 2, size - margin + 8);
}

function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r?: number): void {
  const rad = r ?? Math.min(w, h) / 3;
  g.beginPath();
  g.moveTo(x + rad, y);
  g.arcTo(x + w, y, x + w, y + h, rad);
  g.arcTo(x + w, y + h, x, y + h, rad);
  g.arcTo(x, y + h, x, y, rad);
  g.arcTo(x, y, x + w, y, rad);
  g.closePath();
}
