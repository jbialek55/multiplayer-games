/// „1 z dziesięciu" quiz UI. Shows the question + options, waits for the
/// current player to answer, and tracks scores/lives/elimination. All logic
/// (correctness, elimination, winner) is server-side.
///
/// After every answer the server has already moved on to the next question, so
/// the renderer holds the latest `last_feedback` on screen for a moment
/// ("X answered B - the right answer was C") before showing what comes next.

import type { GameSnapshot } from "../../protocol";
import type { RenderCtx } from "../types";

const LETTERS = ["A", "B", "C", "D"];
const REVEAL_MS = 3000;

interface Question {
  text: string;
  options: string[];
  category: string;
}

interface Feedback {
  n: number;
  player_id: string;
  correct: boolean;
  answer: number;
  correct_answer: number;
  eliminated: boolean;
  question: Question;
}

// undefined = nothing seen yet in this game; null = seen "no feedback yet".
let seenN: number | null | undefined;
let reveal: Feedback | null = null;
let revealTimer: number | undefined;
let latest: { container: HTMLElement; ctx: RenderCtx } | null = null;

/// Forget the previous game (called when a new game starts).
export function resetQuiz(): void {
  window.clearTimeout(revealTimer);
  seenN = undefined;
  reveal = null;
  latest = null;
}

export function renderQuiz(container: HTMLElement, ctx: RenderCtx): void {
  latest = { container, ctx };
  trackFeedback(ctx.snapshot.last_feedback as Feedback | null);
  draw(container, ctx);
}

function trackFeedback(fb: Feedback | null): void {
  if (seenN === undefined) {
    // First snapshot we see (game start, or a rejoin mid-game): don't replay
    // an answer that was given before we got here.
    seenN = fb ? fb.n : null;
    return;
  }
  if (!fb || fb.n === seenN) return;
  seenN = fb.n;
  reveal = fb;
  window.clearTimeout(revealTimer);
  revealTimer = window.setTimeout(() => {
    reveal = null;
    if (latest) draw(latest.container, latest.ctx);
  }, REVEAL_MS);
}

function draw(container: HTMLElement, ctx: RenderCtx): void {
  const { snapshot, me, send } = ctx;
  container.replaceChildren();

  const finished = snapshot.finished;
  const alive = snapshot.alive as string[];
  const myTurn = !reveal && !finished && snapshot.current === me && alive.includes(me ?? "");

  container.appendChild(scoreboard(snapshot, me));

  if (reveal) {
    container.appendChild(revealCard(reveal, me));
    return;
  }

  if (finished) {
    const res = document.createElement("div");
    // The game_over result is authoritative (a forfeit/abandon has no winner in the snapshot).
    const res_ = ctx.result;
    const isDraw = res_ ? res_.draw : Boolean(snapshot.draw);
    const winner = res_ ? res_.winner : (snapshot.winner as string | null);
    const cls = isDraw ? "draw" : winner === me ? "win" : "lose";
    res.className = `quiz-result ${cls}`;
    res.textContent = isDraw ? "Draw!" : winner === me ? "You win!" : "You lose";
    container.appendChild(res);
    return;
  }

  const q = snapshot.question as Question | null;
  if (!q) return;

  const card = questionCard(q);
  const options = card.querySelector(".quiz-options") as HTMLElement;
  q.options.forEach((opt, i) => {
    const btn = optionButton(i, opt);
    btn.disabled = !myTurn;
    btn.addEventListener("click", () => send({ answer: i }));
    options.appendChild(btn);
  });
  container.appendChild(card);

  const hint = document.createElement("div");
  hint.className = "turn-line";
  hint.textContent = myTurn ? "Your turn — pick an answer" : "Waiting for " + waitingFor(snapshot, me) + "…";
  container.appendChild(hint);
}

function scoreboard(snapshot: GameSnapshot, me: string | null): HTMLElement {
  const alive = snapshot.alive as string[];
  const players = snapshot.players as string[];
  const cap = (snapshot.lives_cap as number | undefined) ?? 3;
  const board = document.createElement("div");
  board.className = "quiz-board";
  alive.forEach((pid) => {
    const chip = document.createElement("div");
    chip.className = "quiz-player" + (pid === snapshot.current && !snapshot.finished && !reveal ? " active" : "");
    if (pid === me) chip.classList.add("me");
    const lives = Math.max(0, snapshot.lives[pid] ?? 0);
    chip.append(
      span("qp-name", name(pid, me)),
      span("qp-score", `${snapshot.scores[pid] ?? 0} pkt`),
      span("qp-lives", "●".repeat(lives) + "○".repeat(Math.max(0, cap - lives))),
    );
    board.appendChild(chip);
  });
  players
    .filter((pid) => !alive.includes(pid))
    .forEach((pid) => {
      const chip = document.createElement("div");
      chip.className = "quiz-player eliminated";
      chip.textContent = `${name(pid, me)} — eliminated`;
      board.appendChild(chip);
    });
  return board;
}

function revealCard(fb: Feedback, me: string | null): HTMLElement {
  const card = questionCard(fb.question);
  card.classList.add("quiz-reveal");

  const who = fb.player_id === me ? "You" : name(fb.player_id, me);
  const verdict = document.createElement("div");
  verdict.className = "quiz-verdict " + (fb.correct ? "ok" : "bad");
  verdict.textContent = fb.correct
    ? `${who} answered correctly!`
    : `${who} ${fb.player_id === me ? "were" : "was"} wrong${fb.eliminated ? " — eliminated" : ""}`;
  card.insertBefore(verdict, card.querySelector(".quiz-q"));

  const options = card.querySelector(".quiz-options") as HTMLElement;
  fb.question.options.forEach((opt, i) => {
    const btn = optionButton(i, opt);
    btn.disabled = true;
    if (i === fb.correct_answer) {
      btn.classList.add("correct");
      btn.append(tag(fb.correct ? `${who}'s answer ✓` : "Correct answer ✓"));
    } else if (i === fb.answer) {
      btn.classList.add("wrong");
      btn.append(tag(`${who === "You" ? "Your" : who + "'s"} answer ✗`));
    }
    options.appendChild(btn);
  });
  return card;
}

function questionCard(q: Question): HTMLElement {
  const card = document.createElement("div");
  card.className = "quiz-card";
  card.append(span("quiz-cat", q.category, "div"), span("quiz-q", q.text, "div"));
  const options = document.createElement("div");
  options.className = "quiz-options";
  card.appendChild(options);
  return card;
}

function optionButton(i: number, text: string): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.className = "quiz-opt";
  btn.append(span("quiz-letter", LETTERS[i]), document.createTextNode(text));
  return btn;
}

function tag(text: string): HTMLElement {
  return span("quiz-tag", text);
}

function span(cls: string, text: string, el: "span" | "div" = "span"): HTMLElement {
  const e = document.createElement(el);
  e.className = cls;
  e.textContent = text;
  return e;
}

function waitingFor(snapshot: GameSnapshot, me: string | null): string {
  return snapshot.current && snapshot.current !== me ? name(snapshot.current as string, me) : "your opponent";
}

function name(id: string, me: string | null): string {
  return id === me ? "you" : id.slice(0, 6);
}
