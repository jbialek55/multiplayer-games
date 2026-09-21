"""„1 z dziesięciu" — quiz game session.

Rules (simplified TV-quiz style):
- 2..10 players. Each has 3 lives (``lives``).
- Players answer in round-robin; a correct answer awards +1 point, a wrong
  answer costs a life. At 0 lives a player is eliminated.
- The game ends when one player remains (the winner) or the question pool runs
  out (then the highest scorer wins; a tie is a draw).

The session is authoritative: it validates answer indices and turn ownership,
and never trusts the client for correctness.
"""

from __future__ import annotations

import random
from typing import Any, Sequence

from mp.games.base import Game, GameEvent, GameError, GameSession
from mp.games.quiz.questions import QUESTIONS

DEFAULT_LIVES = 3


class QuizGame(Game):
    def __init__(self) -> None:
        super().__init__(id="quiz", name="Quiz", min_players=2, max_players=10)

    def create_session(self, player_ids: Sequence[str]) -> "QuizSession":
        return QuizSession(player_ids)


class QuizSession(GameSession):
    def __init__(self, player_ids: Sequence[str], lives: int = DEFAULT_LIVES) -> None:
        super().__init__(game_id="quiz", player_ids=player_ids)
        if len(player_ids) < 2 or len(player_ids) > 10:
            raise GameError("quiz requires between 2 and 10 players")
        self.lives_cap = lives
        self.scores: dict[str, int] = {pid: 0 for pid in player_ids}
        self.lives: dict[str, int] = {pid: lives for pid in player_ids}
        self.alive: list[str] = list(player_ids)
        # fresh random order each game; we draw sequentially so nothing repeats
        self.pool = list(QUESTIONS)
        random.shuffle(self.pool)
        self.q_index = 0
        self.cursor = 0  # index into ``alive``
        self.last_feedback: dict[str, Any] | None = None
        self.winner: str | None = None
        self.draw = False
        self.end_reason: str | None = None

    @property
    def current(self) -> str | None:
        if not self.alive:
            return None
        return self.alive[self.cursor % len(self.alive)]

    @staticmethod
    def _public(q: dict) -> dict:
        """The part of a question that is safe to show *before* it is answered."""
        return {"text": q["text"], "options": q["options"], "category": q["category"]}

    def _current_question(self) -> dict | None:
        if self.q_index >= len(self.pool):
            return None
        return self._public(self.pool[self.q_index])

    # --- lifecycle --------------------------------------------------- #
    def start(self) -> list[GameEvent]:
        self.started = True
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    def remove_player(self, player_id: str) -> list[GameEvent]:
        """A player left mid-game: drop them and continue with the rest.

        The game only ends if nobody meaningful remains — the last player
        standing wins (or it becomes a draw if everyone left). It never makes
        an unrelated staying player lose.
        """
        if player_id not in self.player_ids or self.finished:
            return []
        idx = self.alive.index(player_id) if player_id in self.alive else None
        if player_id in self.alive:
            self.alive.remove(player_id)
        self.player_ids.remove(player_id)
        self.scores.pop(player_id, None)
        self.lives.pop(player_id, None)

        if len(self.alive) == 0:
            self.draw = True
            self.finished = True
            self.end_reason = "abandoned"
            return [
                GameEvent(GameEvent.STATE, {"state": self.snapshot()}),
                GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()}),
            ]
        if len(self.alive) == 1:
            self.winner = self.alive[0]
            self.finished = True
            self.end_reason = "last_standing"
            return [
                GameEvent(GameEvent.STATE, {"state": self.snapshot()}),
                GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()}),
            ]
        # otherwise: fix the turn cursor and continue the round-robin
        if idx is not None and idx < self.cursor:
            self.cursor -= 1
        self.cursor = self.cursor % len(self.alive)
        return [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]

    # --- gameplay ---------------------------------------------------- #
    def handle_input(self, player_id: str, action: dict[str, Any]) -> list[GameEvent]:
        if not self.started:
            raise GameError("game not started")
        if self.finished or self.winner is not None or self.draw:
            raise GameError("game is over")
        if self.current != player_id:
            raise GameError("it is not your turn")
        answer = action.get("answer")
        if not isinstance(answer, int) or not (0 <= answer <= 3):
            raise GameError("choose an answer 0-3")

        q = self.pool[self.q_index]
        correct = answer == q["answer"]
        eliminated = False
        if correct:
            self.scores[player_id] += 1
        else:
            self.lives[player_id] -= 1
            if self.lives[player_id] <= 0:
                self.alive.remove(player_id)
                eliminated = True

        # Everything a client needs to show "you answered X, the right one was Y"
        # after the snapshot has already moved on to the next question.
        self.last_feedback = {
            "n": self.q_index,  # unique per answered question
            "player_id": player_id,
            "correct": correct,
            "answer": answer,
            "correct_answer": q["answer"],
            "eliminated": eliminated,
            "question": self._public(q),
        }

        self._advance(eliminated)
        events = [GameEvent(GameEvent.STATE, {"state": self.snapshot()})]
        if self.finished:
            events.append(GameEvent(GameEvent.OVER, {"state": self.snapshot(), "result": self.result()}))
        return events

    def _advance(self, eliminated: bool) -> None:
        """Advance turn cursor and check for game end."""
        q = len(self.pool)
        if len(self.alive) == 1:
            self.winner = self.alive[0]
            self.finished = True
            self.end_reason = "last_standing"
            return
        if self.q_index + 1 >= q:
            # no more questions; decide by score among the alive
            self._decide_by_score()
            self.finished = True
            self.end_reason = "pool_exhausted"
            return

        self.q_index += 1
        if eliminated:
            # The eliminated player was removed from ``alive``, so the next
            # player already slid into this slot; stepping again would skip them.
            self.cursor %= len(self.alive)
        else:
            self.cursor = (self.cursor + 1) % len(self.alive)

    def _decide_by_score(self) -> None:
        top = max((self.scores[pid] for pid in self.alive), default=0)
        leaders = [pid for pid in self.alive if self.scores[pid] == top]
        if len(leaders) == 1:
            self.winner = leaders[0]
        else:
            self.draw = True

    # --- state ------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        return {
            "phase": "question",
            "question": self._current_question(),
            "current": self.current,
            "scores": dict(self.scores),
            "lives": dict(self.lives),
            "lives_cap": self.lives_cap,
            "alive": list(self.alive),
            "players": list(self.player_ids),
            "finished": self.finished,
            "winner": self.winner,
            "draw": self.draw,
            "reason": self.end_reason,
            "last_feedback": self.last_feedback,
        }

    def result(self) -> dict[str, Any]:
        return {
            "winner": self.winner,
            "draw": self.draw,
            "reason": self.end_reason,
            "scores": dict(self.scores),
        }
