"""Chess engine rule tests (pure, deterministic)."""

from __future__ import annotations

from mp.games.chess import game as g


def board_with(pieces: dict[str, str]) -> tuple:
    b = [None] * 64
    for name, pc in pieces.items():
        b[g.parse_sq(name)] = pc
    return tuple(b)


def state_with(pieces, turn=g.WHITE, castling=(True, True, True, True), ep=None, halfmove=0):
    return g.State(board=board_with(pieces), turn=turn, castling=castling, ep=ep, halfmove=halfmove)


def apply_named(state, frm, to, promo=None):
    from_, to_ = g.parse_sq(frm), g.parse_sq(to)
    cands = [
        m
        for m in g.legal_moves(state)
        if m.from_sq == from_
        and m.to_sq == to_
        and (m.promo or "q").lower() == (promo or "q").lower()
    ]
    assert cands, f"no legal move {frm}->{to} ({state.turn})"
    return g.apply_move(state, cands[0])


def test_initial_setup() -> None:
    s = g.initial_state()
    assert s.board[g.parse_sq("a1")] == "R"
    assert s.board[g.parse_sq("e1")] == "K"
    assert s.board[g.parse_sq("a8")] == "r"
    assert s.board[g.parse_sq("e8")] == "k"
    assert s.board[g.parse_sq("d1")] == "Q"
    assert s.turn == g.WHITE


def test_initial_legal_moves_are_twenty() -> None:
    assert len(g.legal_moves(g.initial_state())) == 20


def test_pawn_double_push_sets_en_passant_target() -> None:
    s = state_with(
        {"e5": "P", "d7": "p", "e1": "K", "e8": "k"},
        turn=g.BLACK,
        castling=(False, False, False, False),
    )
    s2 = apply_named(s, "d7", "d5")
    assert s2.ep == g.parse_sq("d6")


def test_en_passant_capture() -> None:
    s = state_with(
        {"e5": "P", "d7": "p", "e1": "K", "e8": "k"},
        turn=g.BLACK,
        castling=(False, False, False, False),
    )
    s2 = apply_named(s, "d7", "d5")
    # white can capture en passant e5xd6
    assert any(
        m.from_sq == g.parse_sq("e5") and m.to_sq == g.parse_sq("d6")
        for m in g.legal_moves(s2)
    )
    s3 = apply_named(s2, "e5", "d6")
    assert s3.board[g.parse_sq("d6")] == "P"
    assert s3.board[g.parse_sq("d5")] is None  # captured pawn removed


def test_promotion_offers_queen_default() -> None:
    s = state_with(
        {"e7": "P", "e1": "K", "a8": "k"}, turn=g.WHITE, castling=(False, False, False, False)
    )
    moves = [m for m in g.legal_moves(s) if m.to_sq == g.parse_sq("e8")]
    assert moves, "promotion move missing"
    assert any((m.promo or "q").lower() == "q" for m in moves)
    s2 = apply_named(s, "e7", "e8", promo="q")
    assert s2.board[g.parse_sq("e8")] == "Q"


def test_kingside_castle_legal_when_clear() -> None:
    s = state_with({"e1": "K", "h1": "R", "e8": "k", "a8": "r"}, turn=g.WHITE)
    assert any(
        m.from_sq == g.parse_sq("e1") and m.to_sq == g.parse_sq("g1")
        for m in g.legal_moves(s)
    )


def test_castle_blocked_by_piece() -> None:
    s = state_with({"e1": "K", "h1": "R", "f1": "R", "e8": "k", "a8": "r"}, turn=g.WHITE)
    assert not any(
        m.from_sq == g.parse_sq("e1") and m.to_sq == g.parse_sq("g1")
        for m in g.legal_moves(s)
    )


def test_castle_blocked_in_check() -> None:
    # black rook e8 checks white king e1 along the rank
    s = state_with({"e1": "K", "h1": "R", "e8": "r"}, turn=g.WHITE)
    assert g.in_check(s, g.WHITE)
    assert not any(
        m.from_sq == g.parse_sq("e1") and m.to_sq == g.parse_sq("g1")
        for m in g.legal_moves(s)
    )


def test_castle_after_king_moved_is_illegal() -> None:
    s = state_with({"e1": "K", "h1": "R", "e8": "k", "a8": "r"}, turn=g.WHITE)
    # simulate the king having moved: clear the right
    s2 = g.State(board=s.board, turn=s.turn, castling=(False, True, True, True))
    assert not any(
        m.from_sq == g.parse_sq("e1") and m.to_sq == g.parse_sq("g1")
        for m in g.legal_moves(s2)
    )


def test_castle_moves_rook() -> None:
    s = state_with({"e1": "K", "h1": "R", "e8": "k", "a8": "r"}, turn=g.WHITE)
    s2 = apply_named(s, "e1", "g1")
    assert s2.board[g.parse_sq("g1")] == "K"
    assert s2.board[g.parse_sq("f1")] == "R"
    assert s2.board[g.parse_sq("h1")] is None
    assert s2.castling[0] is False and s2.castling[1] is False  # white rights cleared


def test_check_detection() -> None:
    s = state_with({"e1": "K", "e8": "r"}, turn=g.WHITE)
    assert g.in_check(s, g.WHITE)


def test_checkmate() -> None:
    # back-rank mate: black king h8, pawns f7/g7/h7, white rook e8
    s = state_with(
        {"h8": "k", "f7": "p", "g7": "p", "h7": "p", "e8": "R", "a1": "K"},
        turn=g.BLACK,
        castling=(False, False, False, False),
    )
    res = g.result(s)
    assert res["winner"] == g.WHITE
    assert res["reason"] == "checkmate"
    assert not g.any_legal(s)


def test_stalemate() -> None:
    s = state_with(
        {"a8": "k", "c7": "K", "b6": "Q"},
        turn=g.BLACK,
        castling=(False, False, False, False),
    )
    assert not g.in_check(s, g.BLACK)
    assert not g.any_legal(s)
    res = g.result(s)
    assert res["draw"] is True
    assert res["reason"] == "stalemate"


def test_two_bishops_are_not_a_draw() -> None:
    # K + two bishops vs K is a win, so it must NOT be an automatic draw
    # (this is what previously prevented checkmate in such endgames).
    s = state_with(
        {"a8": "k", "c6": "K", "f1": "B", "g2": "B"},
        turn=g.BLACK,
        castling=(False, False, False, False),
    )
    assert g.insufficient_material(s.board) is False
    assert g.result(s)["draw"] is False


def test_single_bishop_and_single_knight_are_draws() -> None:
    assert g.insufficient_material(state_with({"a8": "k", "c6": "K", "f1": "B"}, turn=g.BLACK).board)
    assert g.insufficient_material(state_with({"a8": "k", "c6": "K", "f1": "N"}, turn=g.BLACK).board)


def test_fool_s_mate_by_moves() -> None:
    s = g.initial_state()
    s = apply_named(s, "f2", "f3")
    s = apply_named(s, "e7", "e5")
    s = apply_named(s, "g2", "g4")
    s = apply_named(s, "d8", "h4")  # Qh4#
    assert s.turn == g.WHITE
    assert g.in_check(s, g.WHITE)
    res = g.result(s)
    assert res["winner"] == g.BLACK
    assert res["reason"] == "checkmate"


def test_pinned_piece_cannot_expose_king() -> None:
    # black rook e8 pins the white knight e2 to the king e1 along the e-file.
    s = state_with(
        {"e1": "K", "e2": "N", "e8": "r", "a8": "k"}, turn=g.WHITE, castling=(False, False, False, False)
    )
    # every knight move leaves e2, exposing the king to the rook -> none legal.
    assert not any(m.from_sq == g.parse_sq("e2") for m in g.legal_moves(s))
