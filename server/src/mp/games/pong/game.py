"""Pure Pong physics.

Deterministic (given the same inputs + fixed dt), no I/O. The server ticks this
at a fixed rate and decides the outcome; the client only renders the snapshot
and reports a paddle direction (-1 up, 0 none, +1 down); the session turns a
finger "target" position into such directions.
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
RALLY_SPEEDUP = 1.05        # the ball gets 5% faster after every paddle hit...
MAX_SPEED_MULT = 3.0        # ...up to this multiple of the serve speed
WIN_SCORE = 5
SERVE_VX = BALL_SPEED / 2  # horizontal speed of a fresh serve

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
    rally: int = 0  # paddle hits since the last serve (drives the speed-up)


def new_state() -> State:
    return State(ball_x=W / 2, ball_y=H / 2, ball_vx=SERVE_VX, ball_vy=BALL_SPEED / 3,
                 pad_l=H / 2, pad_r=H / 2, score_l=0, score_r=0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def speed_mult(rally: int) -> float:
    """How much faster than the serve the ball travels after ``rally`` hits."""
    return min(MAX_SPEED_MULT, RALLY_SPEEDUP**rally)


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
    rally = state.rally

    # Every paddle hit sends the ball back 5% faster (both axes).
    # left paddle (x in [PAD_W - r, PAD_W + r])
    if vx < 0 and abs(bx - PAD_W) < (PAD_W / 2 + BALL_R) and abs(by - pad_l) <= PAD_H / 2 + BALL_R:
        rally += 1
        bx = PAD_W + PAD_W / 2 + BALL_R
        vx = SERVE_VX * speed_mult(rally)
        vy = (by - pad_l) / (PAD_H / 2) * BALL_SPEED * 0.6 * speed_mult(rally)
    # right paddle
    elif vx > 0 and abs(bx - (W - PAD_W)) < (PAD_W / 2 + BALL_R) and abs(by - pad_r) <= PAD_H / 2 + BALL_R:
        rally += 1
        bx = (W - PAD_W) - PAD_W / 2 - BALL_R
        vx = -SERVE_VX * speed_mult(rally)
        vy = (by - pad_r) / (PAD_H / 2) * BALL_SPEED * 0.6 * speed_mult(rally)

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

    return State(bx, by, vx, vy, pad_l, pad_r, score_l, score_r, winner, rally)


def _serve(prev: State, dir_sign: int, score_l: int, score_r: int) -> State:
    """Reset the ball to centre and serve toward ``dir_sign`` (+1 right, -1 left)."""
    return State(
        ball_x=W / 2,
        ball_y=H / 2,
        ball_vx=dir_sign * SERVE_VX,
        ball_vy=(-1 if (score_l + score_r) % 2 else 1) * BALL_SPEED / 3,
        pad_l=prev.pad_l,
        pad_r=prev.pad_r,
        score_l=score_l,
        score_r=score_r,
        winner=LEFT if score_l >= WIN_SCORE else (RIGHT if score_r >= WIN_SCORE else None),
    )
