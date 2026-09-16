"""Quiz game plugin („1 z dziesięciu" style)."""

from __future__ import annotations

from mp.games.quiz.questions import QUESTIONS
from mp.games.quiz.session import DEFAULT_LIVES, QuizGame, QuizSession

QUIZ = QuizGame()

__all__ = ["QUIZ", "QuizGame", "QuizSession", "QUESTIONS", "DEFAULT_LIVES"]
