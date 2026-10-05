/// Client-side app state. The client only stores what the server told it; it
/// never computes game outcomes. `main.ts` mutates this and calls `render()`.

import type { GameResult, GameSnapshot, RoomInfo } from "./protocol";

export type Screen = "lobby" | "game";

export interface AppState {
  status: string;
  screen: Screen;
  playerId: string | null;
  sessionId: string | null;
  room: RoomInfo | null;
  snapshot: GameSnapshot | null;
  result: GameResult | null;
  rooms: RoomInfo[];
  selectedGame: string;
  rematchVoted: boolean; // whether this player asked for a rematch
  activeGame: string | null; // game of the running session (known even without room info, e.g. after a rejoin)
}

export const state: AppState = {
  status: "connecting…",
  screen: "lobby",
  playerId: null,
  sessionId: null,
  room: null,
  snapshot: null,
  result: null,
  rooms: [],
  selectedGame: "tictactoe",
  rematchVoted: false,
  activeGame: null,
};

/// The game being played (or, in the lobby, the one picked in the picker).
export function currentGameId(): string {
  return state.room?.game_id ?? (state.screen === "game" ? state.activeGame : null) ?? state.selectedGame;
}
