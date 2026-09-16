/// Routes rendering to the right game by its id. Each renderer takes a
/// (container, ctx) where ctx = { snapshot, me, send(action) }.

import type { GameSnapshot } from "../protocol";
import { renderTicTacToe } from "./tictactoe/render";
import { renderChess } from "./chess/render";
import { renderQuiz } from "./quiz/render";
import { renderPong } from "./pong/render";
import { renderSnake } from "./snake/render";

export interface RenderCtx {
  snapshot: GameSnapshot;
  me: string | null;
  send: (action: Record<string, unknown>) => void;
}

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
