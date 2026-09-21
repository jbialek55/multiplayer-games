/// Routes rendering to the right game by its id. Each renderer takes a
/// (container, ctx) where ctx = { snapshot, me, send(action) }.

import type { GameSnapshot } from "../protocol";
import { renderTicTacToe } from "./tictactoe/render";
import { renderChess } from "./chess/render";
import { renderQuiz } from "./quiz/render";
import { pongRole, renderPong } from "./pong/render";
import { renderSnake, snakeRole } from "./snake/render";
import type { RenderCtx, Role } from "./types";

export type { RenderCtx, Role };

type RenderFn = (container: HTMLElement, ctx: RenderCtx) => void;

export const GAME_RENDERERS: Record<string, RenderFn> = {
  tictactoe: renderTicTacToe,
  chess: renderChess,
  quiz: renderQuiz,
  pong: renderPong,
  snake: renderSnake,
};

export const GAME_NAMES: Record<string, string> = {
  tictactoe: "Tic-Tac-Toe",
  chess: "Chess",
  quiz: "Quiz",
  pong: "Pong",
  snake: "Snake Battle",
};

export const QUICK_MATCH_GAMES = ["tictactoe", "chess", "pong"];

/// Colour/side of the player for colour-coded games; null for the others.
export function roleOf(gameId: string, snapshot: GameSnapshot, me: string | null): Role | null {
  if (gameId === "pong") return pongRole(snapshot, me);
  if (gameId === "snake") return snakeRole(snapshot, me);
  return null;
}
