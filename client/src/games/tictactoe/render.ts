/// Tic-Tac-Toe board UI. Renders from a server snapshot and reports a cell
/// intent. No rules live here. Styling is class-based (`.board`, `.cell`).

import type { GameSnapshot } from "../../protocol";

interface Ctx {
  snapshot: GameSnapshot;
  me: string | null;
  send: (action: Record<string, unknown>) => void;
}

// Track the previous board so only freshly-placed marks animate.
let prevBoard: Array<string | null> | null = null;

export function renderTicTacToe(container: HTMLElement, ctx: Ctx): void {
  const { snapshot, me, send } = ctx;
  container.innerHTML = "";

  const grid = document.createElement("div");
  grid.className = "board";
  const canPlay = !snapshot.finished && snapshot.whos_turn === me;
  const board = snapshot.board as Array<string | null>;

  board.forEach((mark, i) => {
    const cell = document.createElement("button");
    cell.className = "cell";
    cell.textContent = mark ?? "";
    cell.disabled = mark !== null || !canPlay;
    if (mark === "X") cell.classList.add("x");
    else if (mark === "O") cell.classList.add("o");
    const justPlaced = mark !== null && (prevBoard == null || prevBoard[i] === null);
    if (justPlaced) cell.classList.add("pop");
    if (canPlay && mark === null) {
      cell.addEventListener("click", () => send({ cell: i }));
    }
    grid.appendChild(cell);
  });

  prevBoard = board;
  container.appendChild(grid);
}

export function resetBoard(): void {
  prevBoard = null;
}
