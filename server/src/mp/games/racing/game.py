"""Simple Racing — pure top-down race engine.

Deterministic grid-checked movement, no I/O. A small predefined rectangular
loop (road ring around a wall island). Cars have simple kinematics
(accel/brake/steer + drag). The server is authoritative for position, speed,
checkpoints, laps and finishing order.

Coordinates: continuous floats in cell units, x right, y down (canvas order).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

# --- track (grid cell units) ---------------------------------------------- #
W = 36
H = 24
# inner island (a wall rectangle) creating the loop
ISLAND = (16, 9, 19, 14)  # (x0, y0, x1, y1) inclusive

CHECKPOINTS = [
    (18.0, 20.0),  # 0 start/finish (bottom-centre)
    (4.0, 12.0),   # 1 left
    (18.0, 4.0),   # 2 top
    (31.0, 12.0),  # 3 right
]
REQUIRED_LAPS = 3
CHECKPOINT_RADIUS = 4.0
START_HEADING = math.pi  # west (counter-clockwise around the loop)

# --- car physics ---------------------------------------------------------- #
ACCEL = 18.0
BRAKE = 34.0
DRAG = 0.55
MAX_SPEED = 26.0
MAX_REVERSE = 9.0
TURN_RATE = 2.6  # rad/sec
BOUNCE = 0.3

PALETTE = ("#3a6ea5", "#c0563f", "#b58a2f", "#4a8a53")


@dataclass(frozen=True)
class Car:
    player_id: str
    x: float
    y: float
    heading: float
    speed: float
    lap: int = 0        # completed laps
    cp_index: int = 1   # next checkpoint to cross
    finished: bool = False
    color: int = 0


@dataclass(frozen=True)
class State:
    cars: tuple[Car, ...]
    tick: int = 0
    winner: str | None = None
    finished: bool = False
    order: tuple[str, ...] = ()


def is_wall(x: float, y: float) -> bool:
    cx, cy = int(x), int(y)
    if cx < 2 or cx >= W - 2 or cy < 2 or cy >= H - 2:
        return True
    x0, y0, x1, y1 = ISLAND
    if x0 <= cx <= x1 and y0 <= cy <= y1:
        return True
    return False


def start_cars(players: list[str]) -> tuple[Car, ...]:
    cars = []
    for i, pid in enumerate(players):
        # staggered on the bottom straight, just right of the start line
        cars.append(
            Car(player_id=pid, x=20.0 + i * 3.0, y=20.0, heading=START_HEADING, speed=0.0, color=i % 4)
        )
    return tuple(cars)


def _move_car(car: Car, inputs: dict, dt: float) -> Car:
    accel = bool(inputs.get("accel"))
    brake = bool(inputs.get("brake"))
    steer = (1 if inputs.get("right") else 0) - (1 if inputs.get("left") else 0)

    sp = car.speed
    if accel:
        sp += ACCEL * dt
    if brake:
        sp += -BRAKE * dt if sp > 0 else -ACCEL * dt
    sp -= sp * DRAG * dt
    sp = max(-MAX_REVERSE, min(MAX_SPEED, sp))
    if abs(sp) < 0.4 and not accel and not brake:
        sp = 0.0

    heading = car.heading
    if abs(sp) > 0.1:
        heading = car.heading + steer * TURN_RATE * dt * (1 if sp >= 0 else -1)

    nx = car.x + math.cos(heading) * sp * dt
    ny = car.y + math.sin(heading) * sp * dt
    if is_wall(nx, ny):
        # hit a wall: keep position, bounce back
        return replace(car, speed=-sp * BOUNCE, heading=car.heading)
    return replace(car, x=nx, y=ny, heading=heading, speed=sp)


def _cross(car: Car) -> Car:
    cp = CHECKPOINTS[car.cp_index]
    dx = car.x - cp[0]
    dy = car.y - cp[1]
    if dx * dx + dy * dy < CHECKPOINT_RADIUS * CHECKPOINT_RADIUS:
        new_lap = car.lap + 1 if car.cp_index == 0 else car.lap
        car = replace(car, cp_index=(car.cp_index + 1) % len(CHECKPOINTS), lap=new_lap)
        if new_lap >= REQUIRED_LAPS:
            car = replace(car, finished=True)
    return car


def step(state: State, inputs: dict[str, dict], dt: float) -> State:
    cars = tuple(_move_car(c, inputs.get(c.player_id, {}), dt) for c in state.cars)
    cars = tuple(_cross(c) for c in cars)

    finished_cars = [c for c in cars if c.finished]
    if finished_cars and not state.finished:
        winner = max(finished_cars, key=lambda c: (c.lap, -cars.index(c)))
        order = tuple(
            c.player_id for c in sorted(cars, key=lambda c: (-c.lap, -c.cp_index, cars.index(c)))
        )
        return State(cars=cars, tick=state.tick + 1, winner=winner.player_id, finished=True, order=order)
    return State(cars=cars, tick=state.tick + 1)
