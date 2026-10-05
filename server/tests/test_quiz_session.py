"""Quiz „1 z dziesięciu" session + question-bank tests."""

from __future__ import annotations

import pytest

from mp.games.base import GameError
from mp.games.quiz.questions import QUESTIONS
from mp.games.quiz.session import QuizGame, QuizSession

P1 = "p1"


def make_session(player_ids=None):
    return QuizSession(player_ids or ["p1", "p2", "p3"])


def test_question_bank_has_at_least_100_well_formed_questions() -> None:
    assert len(QUESTIONS) >= 100
    for q in QUESTIONS:
        assert q["text"]
        assert len(q["options"]) == 4
        assert 0 <= q["answer"] <= 3
        assert q["category"]


def test_requires_two_to_ten_players() -> None:
    with pytest.raises(GameError):
        QuizSession(["only"])
    with pytest.raises(GameError):
        QuizSession([f"p{i}" for i in range(11)])


def test_start_and_turn_order() -> None:
    s = make_session(["p1", "p2"])
    s.start()
    snap = s.snapshot()
    assert snap["current"] == "p1"
    assert snap["lives"] == {"p1": 3, "p2": 3}
    assert snap["question"]["options"]


def test_correct_answer_awards_point_and_advances() -> None:
    s = make_session(["p1", "p2"])
    s.start()
    s.handle_input("p1", {"answer": _correct_for(s)})
    snap2 = s.snapshot()
    assert snap2["scores"]["p1"] == 1
    assert snap2["current"] == "p2"


def test_wrong_answer_costs_a_life() -> None:
    s = make_session(["p1", "p2"])
    s.start()
    n = s.snapshot()["lives"]["p1"]
    s.handle_input("p1", {"answer": _wrong_for(s)})
    assert s.snapshot()["lives"]["p1"] == n - 1


def test_not_your_turn_rejected() -> None:
    s = make_session(["p1", "p2"])
    s.start()
    with pytest.raises(GameError, match="not your turn"):
        s.handle_input("p2", {"answer": 0})


def test_elimination_when_lives_exhausted() -> None:
    s = make_session(["p1", "p2", "p3"])
    s.start()
    for _ in range(40):
        cur = s.current
        if cur is None or s.snapshot()["finished"]:
            break
        # p1 always answers wrong (loses a life); others answer correctly.
        s.handle_input(cur, {"answer": _wrong_for(s) if cur == "p1" else _correct_for(s)})
    assert "p1" not in s.snapshot()["alive"]


def test_next_player_is_not_skipped_after_an_elimination() -> None:
    s = QuizSession(["a", "b", "c"], lives=1)
    s.start()
    s.handle_input("a", {"answer": _correct_for(s)})
    assert s.current == "b"
    s.handle_input("b", {"answer": _wrong_for(s)})  # b's only life -> eliminated
    assert "b" not in s.snapshot()["alive"]
    assert s.current == "c"  # not "a": c is next in the round-robin


def test_elimination_of_the_last_seat_wraps_to_the_first_player() -> None:
    s = QuizSession(["a", "b", "c"], lives=1)
    s.start()
    s.handle_input("a", {"answer": _correct_for(s)})
    s.handle_input("b", {"answer": _correct_for(s)})
    s.handle_input("c", {"answer": _wrong_for(s)})
    assert s.current == "a"


def test_feedback_carries_the_answered_question_and_both_answers() -> None:
    """After answering, the snapshot already shows the *next* question, so the
    feedback has to carry the one that was just answered."""
    s = make_session(["p1", "p2"])
    s.start()
    answered = s.pool[s.q_index]
    wrong = _wrong_for(s)
    s.handle_input("p1", {"answer": wrong})

    snap = s.snapshot()
    fb = snap["last_feedback"]
    assert fb["player_id"] == "p1"
    assert fb["answer"] == wrong
    assert fb["correct_answer"] == answered["answer"]
    assert fb["correct"] is False
    assert fb["question"]["text"] == answered["text"]
    assert fb["question"]["options"] == answered["options"]
    assert snap["question"]["text"] != answered["text"]  # moved on
    assert "answer" not in snap["question"]  # unanswered questions never leak the key


def test_feedback_number_changes_with_every_answer() -> None:
    s = make_session(["p1", "p2"])
    s.start()
    s.handle_input("p1", {"answer": _correct_for(s)})
    first = s.snapshot()["last_feedback"]["n"]
    s.handle_input("p2", {"answer": _correct_for(s)})
    assert s.snapshot()["last_feedback"]["n"] != first


def test_remove_player_continues_game() -> None:
    s = make_session(["p1", "p2", "p3"])
    s.start()
    events = s.remove_player("p3")
    snap = s.snapshot()
    assert "p3" not in snap["alive"]
    assert not snap["finished"]  # game keeps going for the rest
    assert snap["current"] in ("p1", "p2")


def test_remove_player_last_standing_wins() -> None:
    s = make_session(["p1", "p2"])
    s.start()
    events = s.remove_player("p2")
    snap = s.snapshot()
    assert snap["finished"]
    assert snap["winner"] == "p1"  # the staying player wins, never loses


def _correct_for(s) -> int:
    q = s.pool[s.q_index]
    return q["answer"]


def _wrong_for(s) -> int:
    q = s.pool[s.q_index]
    return (q["answer"] + 1) % 4


def test_forfeit_records_winner_in_snapshot() -> None:
    """A forfeited quiz must report the remaining player as the winner."""
    from mp.games.quiz.session import QuizSession

    s = QuizSession(["a", "b"])
    s.start()
    s.mark_finished("b", "forfeit")
    snap = s.snapshot()
    assert snap["finished"] and snap["winner"] == "b" and not snap["draw"]
