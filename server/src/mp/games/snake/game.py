"""Pure Snake Battle engine.

Grid-based, deterministic, no I/O. 2..4 snakes share a board; each tick the
server advances all snakes simultaneously, then resolves collisions with a
fixed, unambiguous rule set (so a simultaneous multi-death is deterministic).

Snake lives in ``tuple[int, int]`` cells as ``(x, y)`` with x=file, y=rank,
grid size ``W x H``. The movement tick takes one input snapshot and returns the
new state (deaths, growth, food, winner) — the sim is replayable in tests.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

W = 20
H = 20

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
DIRS = {"up": UP, "down": DOWN, "left": LEFT, "right": RIGHT}
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

TARGET_FOOD = 3
INITIAL_LENGTH = 3
# classic palette indexed by a snake's ``color``
PALETTE = ("#3a6ea5", "#c0563f", "#b58a2f", "#4a8a53")


@dataclass(frozen=True)
class Snake:
    player_id: str
    body: tuple[tuple[int, int], ...]  # index 0 = head
    dir: tuple[int, int]
    next_dir: tuple[int, int]
    alive: bool
    color: int  # palette index
    score: int


@dataclass(frozen=True)
class State:
    snakes: tuple[Snake, ...]
    food: tuple[tuple[int, int], ...] = ()
    tick: int = 0
    winner: str | None = None
    final_round: bool = False  # set once deaths decide the round is over


def start_positions(order: list[str]) -> tuple[Snake, ...]:
    """Spawn up to 4 snakes around the edges, each facing the centre."""
    h = H // 2
    w = W // 2
    starts = [
        ((6, h), RIGHT, ((6, h), (5, h), (4, h))),
        ((W - 7, h), LEFT, ((W - 7, h), (W - 6, h), (W - 5, h))),
        ((w, 6), DOWN, ((w, 6), (w, 5), (w, 4))),
        ((w, H - 7), UP, ((w, H - 7), (w, H - 6), (w, H - 5))),
    ]
    snakes = []
    for i, pid in enumerate(order):
        _, d, body = starts[i % 4]
        snakes.append(
            Snake(player_id=pid, body=body, dir=d, next_dir=d, alive=True, color=i % 4, score=0)
        )
    return tuple(snakes)


def spawn_initial_food(snakes: tuple[Snake, ...]) -> tuple[tuple[int, int], ...]:
    return _spawn_food(snakes, frozenset())


def _spawn_food(snakes: tuple[Snake, ...], keep: frozenset) -> tuple[tuple[int, int], ...]:
    occupied = {cell for s in snakes if s.alive for cell in s.body}
    free = [(x, y) for x in range(W) for y in range(H) if (x, y) not in occupied and (x, y) not in keep]
    want = TARGET_FOOD - len(keep)
    if want <= 0 or not free:
        return tuple(keep)
    picks = random.sample(free, min(want, len(free)))
    return tuple(keep) + tuple(picks)


def tiebreak(snakes: tuple[Snake, ...]) -> str | None:
    """Deterministic winner among snakes (used when several die together)."""
    if not snakes:
        return None
    best = max(range(len(snakes)), key=lambda i: (snakes[i].score, len(snakes[i].body), -i))
    return snakes[best].player_id


def step(state: State) -> State:
    """Advance one tick: move every alive snake, then resolve collisions."""
    eaten: set[tuple[int, int]] = set()

    # 1) move each snake (buffer next_dir, but forbid instant reversal)
    moved: list[Snake] = []
    for i, s in enumerate(state.snakes):
        if not s.alive:
            moved.append(s)
            continue
        d = s.next_dir if OPPOSITE[s.dir] != s.next_dir else s.dir
        hx, hy = s.body[0]
        nx, ny = hx + d[0], hy + d[1]
        # out of bounds -> dead
        if not (0 <= nx < W and 0 <= ny < H):
            moved.append(replace(s, alive=False, dir=d, next_dir=d))
            continue
        grew = (nx, ny) in state.food and (nx, ny) not in eaten
        if grew:
            eaten.add((nx, ny))
        # new body (tail stays when growing)
        new_body = ((nx, ny),) + (s.body if grew else s.body[:-1])
        moved.append(replace(s, body=new_body, dir=d, next_dir=d, score=s.score + (1 if grew else 0)))

    # 2) detect collisions against the post-move bodies
    body_of: dict[int, tuple] = {}
    for i, s in enumerate(moved):
        if s.alive:
            body_of[i] = s.body
    dead = set()
    for i in body_of:  # alive snakes, post-move
        head = moved[i].body[0]
        if head in moved[i].body[1:]:  # ran into itself
            dead.add(i)
            continue
        for j in body_of:
            if i == j:
                continue
            if head in body_of[j]:  # ran into another snake
                dead.add(i)
                break

    for i in dead:
        moved[i] = replace(moved[i], alive=False)
    still_alive = [i for i in range(len(moved)) if moved[i].alive]

    # remove food that was eaten
    food = tuple(f for f in state.food if f not in eaten)
    food = _spawn_food(moved, frozenset(food))

    # 3) determine the round outcome
    winner = None
    final_round = False
    if len(still_alive) == 0:
        # deterministic tie-break among all snakes: score, then length, then index
        best = max(
            range(len(moved)),
            key=lambda i: (moved[i].score, len(moved[i].body), -i),
        )
        winner = moved[best].player_id
        final_round = True
    elif len(still_alive) == 1:
        winner = moved[still_alive[0]].player_id
        final_round = True

    return State(snakes=tuple(moved), food=food, tick=state.tick + 1, winner=winner, final_round=final_round)
