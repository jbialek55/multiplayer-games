/// „1 z dziesięciu" quiz UI. Shows the question + options, waits for the
/// current player to answer, and tracks scores/lives/elimination. All logic
/// (correctness, elimination, winner) is server-side.

import type { GameSnapshot } from "../../protocol";

const LETTERS = ["A", "B", "C", "D"];

interface Ctx {
  snapshot: GameSnapshot;
  me: string | null;
  send: (action: Record<string, unknown>) => void;
}

export function renderQuiz(container: HTMLElement, ctx: Ctx): void {
  const { snapshot, me, send } = ctx;
  container.innerHTML = "";

  const finished = snapshot.finished;
  const alive = snapshot.alive as string[];
  const players = snapshot.players as string[];
  const myTurn = !finished && snapshot.current === me && alive.includes(me ?? "");
  const q = snapshot.question as { text: string; options: string[]; category: string } | null;

  // players scoreboard
  const board = document.createElement("div");
  board.className = "quiz-board";
  alive.forEach((pid) => {
    const chip = document.createElement("div");
    chip.className = "quiz-player" + (pid === snapshot.current && !finished ? " active" : "");
    if (pid === me) chip.classList.add("me");
    const score = snapshot.scores[pid] ?? 0;
    const lives = snapshot.lives[pid] ?? 0;
    chip.innerHTML =
      `<span class="qp-name">${pid === me ? "you" : short(pid)}</span>` +
      `<span class="qp-score">${score} pkt</span>` +
      `<span class="qp-lives">${"●".repeat(Math.max(0, lives))}${"○".repeat(Math.max(0, 3 - lives))}</span>`;
    board.appendChild(chip);
  });
  // show eliminated players greyed
  players
    .filter((pid) => !alive.includes(pid))
    .forEach((pid) => {
      const chip = document.createElement("div");
      chip.className = "quiz-player eliminated";
      chip.textContent = `${pid === me ? "you" : short(pid)} — eliminated`;
      board.appendChild(chip);
    });
  container.appendChild(board);

  if (finished) {
    const res = document.createElement("div");
    const cls = snapshot.draw ? "draw" : snapshot.winner === me ? "win" : "lose";
    res.className = `quiz-result ${cls}`;
    res.textContent = snapshot.draw
      ? "Draw!"
      : snapshot.winner === me
        ? "You win!"
        : "You lose";
    container.appendChild(res);
    return;
  }

  if (!q) return;

  const card = document.createElement("div");
  card.className = "quiz-card";

  const cat = document.createElement("div");
  cat.className = "quiz-cat";
  cat.textContent = q.category;
  card.appendChild(cat);

  const text = document.createElement("div");
  text.className = "quiz-q";
  text.textContent = q.text;
  card.appendChild(text);

  const options = document.createElement("div");
  options.className = "quiz-options";
  q.options.forEach((opt, i) => {
    const btn = document.createElement("button");
    btn.className = "quiz-opt";
    btn.innerHTML = `<span class="quiz-letter">${LETTERS[i]}</span>${opt}`;
    btn.disabled = !myTurn;
    btn.addEventListener("click", () => send({ answer: i }));
    options.appendChild(btn);
  });
  card.appendChild(options);
  container.appendChild(card);

  const hint = document.createElement("div");
  hint.className = "turn-line";
  hint.textContent = myTurn ? "Your turn — pick an answer" : "Waiting for your opponent…";
  container.appendChild(hint);
}

function short(id: string): string {
  return id.slice(0, 6);
}
