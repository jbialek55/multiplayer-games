"""Snake Battle engine unit tests (pure, deterministic)."""

from __future__ import annotations

from mp.games.snake import game as g
from mp.games.snake.game import Snake, State


def mk(pid, body, d, next_dir=None, alive=True, color=0, score=0) -> Snake:
    return Snake(player_id=pid, body=tuple(body), dir=d, next_dir=next_dir or d, alive=alive, color=color, score=score)


def one(pid, body, d, food=(), next_dir=None) -> State:
    return State(snakes=(mk(pid, body, d, next_dir=next_dir),), food=tuple(food))


def test_start_positions_spread() -> None:
    snakes = g.start_positions(["a", "b", "c", "d"])
    assert len(snakes) == 4
    assert all(s.alive for s in snakes)
    heads = {s.body[0] for s in snakes}
    assert len(heads) == 4  # distinct starting cells


def test_snake_moves_each_tick() -> None:
    st = one("a", [(5, 5), (4, 5), (3, 5)], g.RIGHT, food=())
    s2 = g.step(st)
    assert s2.snakes[0].body[0] == (6, 5)


def test_eating_grows_and_scores() -> None:
    st = one("a", [(5, 5), (4, 5), (3, 5)], g.RIGHT, food=((6, 5),))
    s2 = g.step(st)
    snake = s2.snakes[0]
    assert snake.body[0] == (6, 5)
    assert len(snake.body) == 4  # grew by one
    assert snake.score == 1
    assert (6, 5) not in s2.food  # food consumed


def test_boundary_death() -> None:
    st = one("a", [(g.W - 1, 5), (g.W - 2, 5), (g.W - 3, 5)], g.RIGHT)
    s2 = g.step(st)
    assert s2.snakes[0].alive is False


def test_self_collision_dies() -> None:
    body = [(3, 3), (3, 4), (2, 4), (2, 3), (2, 2)]
    st = one("a", body, g.DOWN)  # moving down into its own neck at (3,4)
    s2 = g.step(st)
    assert s2.snakes[0].alive is False


def test_head_on_collision_kills_both() -> None:
    a = mk("a", [(5, 5), (4, 5), (3, 5)], g.RIGHT, next_dir=g.RIGHT)
    b = mk("b", [(7, 5), (8, 5), (9, 5)], g.LEFT, next_dir=g.LEFT, color=1)
    st = State(snakes=(a, b), food=())
    s2 = g.step(st)
    assert s2.snakes[0].alive is False
    assert s2.snakes[1].alive is False


def test_no_instant_reverse() -> None:
    a = mk("a", [(5, 5), (4, 5), (3, 5)], g.RIGHT, next_dir=g.LEFT)
    st = State(snakes=(a,), food=())
    s2 = g.step(st)
    # reverse ignored -> it kept moving right
    assert s2.snakes[0].body[0] == (6, 5)
    assert s2.snakes[0].dir == g.RIGHT


def test_survivor_wins_when_one_remains() -> None:
    a = mk("a", [(2, 5), (1, 5), (0, 5)], g.RIGHT)
    b = mk("b", [(g.W - 1, 5), (g.W - 2, 5), (g.W - 3, 5)], g.RIGHT, color=1)
    # b is heading into the wall -> dies; a survives -> a wins
    st = State(snakes=(a, b), food=())
    s2 = g.step(st)
    assert s2.winner == "a"
    assert s2.final_round


def test_tiebreak_is_deterministic() -> None:
    # both snakes dead; winner is decided by score then length then index
    a = mk("a", [(1, 1), (1, 2)], g.UP, alive=False, score=2)
    b = mk("b", [(2, 2), (2, 3), (2, 4)], g.LEFT, alive=False, score=1, color=1)
    st = State(snakes=(a, b), food=())
    s2 = g.step(st)  # no alive snakes -> not any new movement, but recompute is inert
    # Direct call is the source of truth:
    assert g.tiebreak((a, b)) == "a"
