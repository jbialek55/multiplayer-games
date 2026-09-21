/// Shared wire protocol types + game snapshot. Mirror of the server's
/// `mp/protocol/messages.py`. The client is a "dumb" renderer: it never
/// computes authoritative game state.

export type MessageType =
  // client -> server
  | "hello"
  | "rejoin"
  | "create_room"
  | "join_room"
  | "leave_room"
  | "list_rooms"
  | "find_match"
  | "cancel_match"
  | "start_game"
  | "rematch"
  | "game_action"
  | "ping"
  // server -> client
  | "hello_ack"
  | "room_created"
  | "room_joined"
  | "room_left"
  | "room_update"
  | "room_list"
  | "queue_ack"
  | "match_found"
  | "game_started"
  | "state_update"
  | "game_over"
  | "peer_disconnected"
  | "peer_reconnected"
  | "rematch_requested"
  | "pong"
  | "error";

export interface Envelope {
  type: MessageType;
  seq?: number;
  payload: Record<string, unknown>;
}

export interface RoomInfo {
  id: string;
  game_id: string;
  host_id: string;
  players: string[];
  status: "waiting" | "playing" | "closed";
}

/// A game-specific snapshot. Games expose different fields (a tic-tac-toe
/// board, a chess board + legal moves, a quiz question), so it is deliberately
/// loosely typed; each game's renderer knows its own shape.
export type GameSnapshot = Record<string, any>;

export interface GameResult {
  winner: string | null; // player_id or a symbol
  draw: boolean;
  reason?: string;
  winning_line?: number[] | null;
}

export const STORAGE = {
  playerId: "mp.playerId",
  sessionId: "mp.sessionId",
};
