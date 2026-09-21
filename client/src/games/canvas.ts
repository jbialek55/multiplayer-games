/// Small canvas helpers shared by the canvas-based games (pong, snake).

export function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
}

/// Dim the whole canvas so an overlay message is readable.
export function dim(g: CanvasRenderingContext2D, size: number, alpha = 0.6): void {
  g.fillStyle = `rgba(0,0,0,${alpha})`;
  g.fillRect(0, 0, size, size);
}

/// A coloured pill with a label, centred on (cx, cy). Used for "You are BLUE".
export function pill(g: CanvasRenderingContext2D, cx: number, cy: number, text: string, color: string, fontPx: number): void {
  g.font = `800 ${fontPx}px system-ui, sans-serif`;
  const padX = fontPx * 0.9;
  const w = g.measureText(text).width + padX * 2;
  const h = fontPx * 1.9;
  g.fillStyle = color;
  roundRect(g, cx - w / 2, cy - h / 2, w, h, h / 2);
  g.fill();
  g.strokeStyle = "rgba(255,255,255,0.85)";
  g.lineWidth = 3;
  g.stroke();
  g.fillStyle = "#fff";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(text, cx, cy + 1);
}
