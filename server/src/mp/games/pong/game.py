"""Pure Pong physics.

Deterministic (given the same inputs + fixed dt), no I/O. The server ticks this
at a fixed rate and decides the outcome; the client only renders the snapshot
and reports held arrow keys as a paddle direction (-1 up, 0 none, +1 down).
"""

from __future__ import annotations

from dataclasses import dataclass

W = 100.0  # x: 0..100
H = 100.0  # y: 0..100
PAD_H = 22.0
PAD_W = 5.0
PAD_SPEED = 45.0            # units/sec
BALL_R = 2.0
BALL_SPEED = 78.0           # units/sec (magnitude of vx/vy components combined)
WIN_SCORE = 5

LEFT = "L"
RIGHT = "R"
SIDES = (LEFT, RIGHT)


@dataclass(frozen=True)
class State:
    ball_x: float
    ball_y: float
    ball_vx: float
    ball_vy: float
    pad_l: float  # left paddle centre y
    pad_r: float  # right paddle centre y
    score_l: int
    score_r: int
    winner: str | None = None  # side that won, or None


def new_state() -> State:
    return State(ball_x=W / 2, ball_y=H / 2, ball_vx=BALL_SPEED / 2, ball_vy=BALL_SPEED / 3,
                 pad_l=H / 2, pad_r=H / 2, score_l=0, score_r=0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def step(state: State, dir_l: int, dir_r: int, dt: float) -> State:
    """Advance one tick given the held direction for each paddle."""
    # paddles
    pad_l = _clamp(state.pad_l + dir_l * PAD_SPEED * dt, PAD_H / 2, H - PAD_H / 2)
    pad_r = _clamp(state.pad_r + dir_r * PAD_SPEED * dt, PAD_H / 2, H - PAD_H / 2)

    # ball
    bx = state.ball_x + state.ball_vx * dt
    by = state.ball_y + state.ball_vy * dt
    vx, vy = state.ball_vx, state.ball_vy

    # top/bottom bounce
    if by < BALL_R:
        by = BALL_R
        vy = abs(vy)
    elif by > H - BALL_R:
        by = H - BALL_R
        vy = -abs(vy)

    # paddle collisions (check when the ball is near the paddle's x plane)
    score_l, score_r = state.score_l, state.score_r
    winner = state.winner

    # left paddle (x in [PAD_W - r, PAD_W + r])
    if vx < 0 and abs(bx - PAD_W) < (PAD_W / 2 + BALL_R) and abs(by - pad_l) <= PAD_H / 2 + BALL_R:
        bx = PAD_W + PAD_W / 2 + BALL_R
        vx = abs(vx)
        vy = (by - pad_l) / (PAD_H / 2) * BALL_SPEED * 0.6
    # right paddle
    elif vx > 0 and abs(bx - (W - PAD_W)) < (PAD_W / 2 + BALL_R) and abs(by - pad_r) <= PAD_H / 2 + BALL_R:
        bx = (W - PAD_W) - PAD_W / 2 - BALL_R
        vx = -abs(vx)
        vy = (by - pad_r) / (PAD_H / 2) * BALL_SPEED * 0.6

    # scoring: ball passed a paddle
    if bx < -BALL_R:
        score_r += 1
        return _serve(state, 1, score_l=score_l, score_r=score_r)
    if bx > W + BALL_R:
        score_l += 1
        return _serve(state, -1, score_l=score_l, score_r=score_r)

    if score_l >= WIN_SCORE:
        winner = LEFT
    elif score_r >= WIN_SCORE:
        winner = RIGHT
    else:
        winner = None

    return State(bx, by, vx, vy, pad_l, pad_r, score_l, score_r, winner)


def _serve(prev: State, dir_sign: int, score_l: int, score_r: int) -> State:
    """Reset the ball to centre and serve toward ``dir_sign`` (+1 right, -1 left)."""
    return State(
        ball_x=W / 2,
        ball_y=H / 2,
        ball_vx=dir_sign * BALL_SPEED / 2,
        ball_vy=(-1 if (score_l + score_r) % 2 else 1) * BALL_SPEED / 3,
        pad_l=prev.pad_l,
        pad_r=prev.pad_r,
        score_l=score_l,
        score_r=score_r,
        winner=LEFT if score_l >= WIN_SCORE else (RIGHT if score_r >= WIN_SCORE else None),
    )
