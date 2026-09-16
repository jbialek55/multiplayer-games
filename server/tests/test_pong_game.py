"""Pong physics unit tests (deterministic)."""

from __future__ import annotations

from mp.games.pong import game as g

DT = 0.033


def test_initial_state():
    s = g.new_state()
    assert s.ball_x == g.W / 2 and s.ball_y == g.H / 2
    assert s.pad_l == s.pad_r == g.H / 2
    assert s.winner is None


def test_ball_moves():
    s = g.new_state()
    s2 = g.step(s, 0, 0, DT)
    assert s2.ball_x != s.ball_x  # ball travelled
    assert s2.pad_l == s.pad_r == g.H / 2  # paddles untouched


def test_paddle_moves_with_input():
    s = g.new_state()
    s2 = g.step(s, -1, 1, DT)
    assert s2.pad_l < g.H / 2  # left moved up
    assert s2.pad_r > g.H / 2  # right moved down


def test_paddles_clamped_to_floor():
    s = g.State(
        ball_x=g.W / 2, ball_y=g.H / 2, ball_vx=0, ball_vy=0,
        pad_l=g.H - g.PAD_H / 2, pad_r=g.PAD_H / 2, score_l=0, score_r=0,
    )
    s2 = g.step(s, 1, -1, DT)
    assert s2.pad_l <= g.H - g.PAD_H / 2
    assert s2.pad_r >= g.PAD_H / 2


def test_vertical_bounce():
    s = g.State(
        ball_x=g.W / 2, ball_y=g.BALL_R + 0.01, ball_vx=g.BALL_SPEED / 2, ball_vy=-g.BALL_SPEED,
        pad_l=g.H / 2, pad_r=g.H / 2, score_l=0, score_r=0,
    )
    s2 = g.step(s, 0, 0, DT)
    assert s2.ball_vy > 0  # bounced back down
    assert g.BALL_R - 0.5 <= s2.ball_y <= g.BALL_R + 1  # pinned to the wall


def test_left_paddle_bounce_reverses():
    # ball close to the left paddle and moving left, aligned vertically
    s = g.State(
        ball_x=g.PAD_W + 0.1, ball_y=g.H / 2, ball_vx=-g.BALL_SPEED, ball_vy=0,
        pad_l=g.H / 2, pad_r=g.H / 2, score_l=0, score_r=0,
    )
    s2 = g.step(s, 0, 0, DT)
    assert s2.ball_vx > 0  # reflected toward the right


def test_score_right_when_ball_passes_left():
    s = g.State(
        ball_x=0.01, ball_y=10.0, ball_vx=-g.BALL_SPEED, ball_vy=0,
        pad_l=50.0, pad_r=50.0, score_l=0, score_r=0,
    )
    s2 = g.step(s, 0, 0, 1.0)  # large dt so it clearly passes the wall
    assert s2.score_r == 1
    assert s2.ball_x == g.W / 2  # reset to centre


def test_win_at_win_score():
    s = g.State(
        ball_x=g.W + 1, ball_y=10.0, ball_vx=g.BALL_SPEED, ball_vy=0,
        pad_l=50.0, pad_r=50.0, score_l=g.WIN_SCORE - 1, score_r=0,
    )
    s2 = g.step(s, 0, 0, 1.0)
    assert s2.score_l == g.WIN_SCORE
    assert s2.winner == g.LEFT
