/// Client-side app state + a tiny render trigger. The client only stores what
/// the server told it; it never computes game outcomes.

import type { GameResult, GameSnapshot, RoomInfo } from "./protocol";

export type Screen = "lobby" | "game";

export interface AppState {
  status: string;
  screen: Screen;
  playerId: string | null;
  mySymbol: string | null;
  sessionId: string | null;
  room: RoomInfo | null;
  snapshot: GameSnapshot | null;
  result: GameResult | null;
  rooms: RoomInfo[];
  notice: string | null; // transient banner (opponent disconnected, etc.)
  selectedGame: string;
  rematchVoted: boolean; // whether this player asked for a rematch
}

export const state: AppState = {
  status: "connecting…",
  screen: "lobby",
  playerId: null,
  mySymbol: null,
  sessionId: null,
  room: null,
  snapshot: null,
  result: null,
  rooms: [],
  notice: null,
  selectedGame: "tictactoe",
  rematchVoted: false,
};

const listeners = new Set<() => void>();
export function subscribe(fn: () => void): void {
  listeners.add(fn);
}
export function emit(): void {
  listeners.forEach((fn) => fn());
}

export function notify(text: string | null): void {
  state.notice = text;
  emit();
}
