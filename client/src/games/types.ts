import type { GameSnapshot } from "../protocol";

/// What every game renderer receives on each snapshot.
export interface RenderCtx {
  snapshot: GameSnapshot;
  me: string | null;
  send: (action: Record<string, unknown>) => void;
}

/// "Who am I" for the header chip: a label and, for colour-coded games, the
/// colour the player is drawn in.
export interface Role {
  label: string;
  color?: string;
}
