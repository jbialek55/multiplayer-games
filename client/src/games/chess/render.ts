/// Chess Board UI. Renders the 8x8 board from a server snapshot, lets the
/// player select one of their pieces, highlights every legal destination
/// (from the authoritative `legal_moves`), and sends a move on click.
/// Selection re-renders the board so the possible moves appear immediately.

import type { GameSnapshot } from "../../protocol";

const GLYPH: Record<string, string> = {
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟",
};

const FILES = "abcdefgh";

interface Ctx {
  snapshot: GameSnapshot;
  me: string | null;
  send: (action: Record<string, unknown>) => void;
}

// keep selection across re-renders (state updates)
let selected: string | null = null;

// clear the stale selection when a brand-new game begins
export function resetChess(): void {
  selected = null;
}

function isWhitePiece(piece: string | null): boolean {
  return !!piece && piece === piece.toUpperCase();
}

export function renderChess(container: HTMLElement, ctx: Ctx): void {
  const { snapshot, me, send } = ctx;
  const myColor = snapshot.symbols[me ?? ""] ?? null;
  const myTurn = !snapshot.finished && myColor === snapshot.turn;
  const legal = (snapshot.legal_moves ?? []) as Array<{ from: string; to: string }>;
  const byFrom = new Map<string, string[]>();
  legal.forEach((m) => byFrom.set(m.from, [...(byFrom.get(m.from) ?? []), m.to]));
  const targets = new Set(selected ? (byFrom.get(selected) ?? []) : []);
  const board = snapshot.board as Array<Array<string | null>>;

  container.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "chess";

  board.forEach((row, r) => {
    row.forEach((piece, f) => {
      const square = FILES[f] + String(8 - r);
      const btn = document.createElement("button");
      const dark = (r + f) % 2 === 1; // a8 is light
      btn.className = "sq" + (dark ? " dark" : " light");
      btn.textContent = piece ? GLYPH[piece] : "";
      if (piece) btn.classList.add(isWhitePiece(piece) ? "w" : "b");
      if (selected === square) btn.classList.add("selected");
      if (targets.has(square)) btn.classList.add("target");
      if (snapshot.last && (snapshot.last.from === square || snapshot.last.to === square)) {
        btn.classList.add("lastmove");
      }

      const mine = myColor === "white" ? isWhitePiece(piece) : !!piece && !isWhitePiece(piece);
      btn.addEventListener("click", () => {
        if (snapshot.finished) return;
        if (myTurn && targets.has(square) && selected) {
          send({ from: selected, to: square });
          selected = null;
        } else if (mine && myTurn) {
          selected = selected === square ? null : square;
        } else {
          selected = null;
        }
        // Re-render immediately so the possible moves highlight and update.
        renderChess(container, ctx);
      });
      grid.appendChild(btn);
    });
  });

  container.appendChild(grid);
}
