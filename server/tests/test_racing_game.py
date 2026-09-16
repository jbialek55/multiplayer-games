"""Simple Racing engine unit tests (pure, deterministic)."""

from __future__ import annotations

from mp.games.racing import game as g
from mp.games.racing.game import Car, State, start_cars


def car(pid, x, y, cp_index=1, lap=0, heading=g.START_HEADING, speed=0.0, finished=False, color=0) -> Car:
    return Car(player_id=pid, x=x, y=y, heading=heading, speed=speed, lap=lap, cp_index=cp_index, finished=finished, color=color)


def st(cars) -> State:
    return State(cars=tuple(cars))


def test_start_positions_spread() -> None:
    cars = start_cars(["a", "b", "c"])
    assert len(cars) == 3
    xs = [c.x for c in cars]
    assert len(set(map(int, xs))) == 3  # distinct start x
    assert all(abs(c.y - 20) < 0.01 for c in cars)


def test_car_accelerates() -> None:
    s = st([car("a", 20.0, 20.0)])
    s2 = g.step(s, {"a": {"accel": True}}, 0.1)
    assert s2.cars[0].speed > 0


def test_car_moves_toward_heading() -> None:
    # heading west -> x decreases over ticks
    s = st([car("a", 20.0, 20.0)])
    s2 = g.step(s, {"a": {"accel": True}}, 0.1)
    assert s2.cars[0].x < 20.0


def test_wall_stops_car() -> None:
    # heading west into the left wall
    s = st([car("a", 2.2, 12.0, heading=3.14159, speed=8.0)])
    s2 = g.step(s, {}, 0.1)
    assert abs(s2.cars[0].x - 2.2) < 0.01  # did not pass the wall (kept position)
    assert s2.cars[0].speed < 8.0  # bounced / slowed


def test_checkpoint_advances_in_order() -> None:
    s = st([car("a", 5.0, 12.0, cp_index=1)])  # next checkpoint = left (4,12)
    s2 = g.step(s, {}, 0.05)
    assert s2.cars[0].cp_index == 2


def test_crossing_finish_increments_lap() -> None:
    s = st([car("a", 18.5, 20.0, cp_index=0, lap=1)])  # next = start/finish (18,20)
    s2 = g.step(s, {}, 0.05)
    assert s2.cars[0].lap == 2
    assert s2.cars[0].cp_index == 1


def test_race_finishes_when_lap_reached() -> None:
    s = st([car("a", 18.5, 20.0, cp_index=0, lap=g.REQUIRED_LAPS - 1)])
    s2 = g.step(s, {}, 0.05)
    assert s2.finished
    assert s2.winner == "a"
    assert s2.order == ("a",)


def test_ranking_by_progress_is_deterministic() -> None:
    # two cars finishing the same tick -> lower index wins deterministically
    a = car("a", 18.2, 20.0, cp_index=0, lap=g.REQUIRED_LAPS - 1)
    b = car("b", 18.8, 20.0, cp_index=0, lap=g.REQUIRED_LAPS - 1, color=1)
    s2 = g.step(st([a, b]), {}, 0.05)
    assert s2.finished
    assert s2.winner == "a"  # first car in order wins on tie
    assert len(s2.order) == 2
    assert s2.order[0] == "a"
