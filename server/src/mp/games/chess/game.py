"""Pure chess rules.

Deterministic, immutable, no I/O. Handles every rule: piece movement,
castling (both sides, all conditions), en passant, promotion (auto-queen),
check, checkmate, stalemate, and the 50-move draw. This module is the most
tested part of the game and is what makes the game replayable.

Square indexing:
    index = rank*8 + file, file 0..7 = a..h, rank 0 = white's first rank.
    so a1=0, h1=7, a8=56, h8=63.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

WHITE = "white"
BLACK = "black"
COLORS = (WHITE, BLACK)

# --- squares ------------------------------------------------------------- #
FILES = "abcdefgh"


def sq_name(idx: int) -> str:
    return FILES[idx % 8] + str(idx // 8 + 1)


def parse_sq(name: str) -> int:
    file = FILES.index(name[0].lower())
    rank = int(name[1]) - 1
    return rank * 8 + file


def _file(idx: int) -> int:
    return idx % 8


def _rank(idx: int) -> int:
    return idx // 8


def _idx(f: int, r: int) -> int:
    return r * 8 + f


def _on(f: int, r: int) -> bool:
    return 0 <= f < 8 and 0 <= r < 8


# --- pieces --------------------------------------------------------------- #
def color_of(piece: str) -> str:
    return WHITE if piece.isupper() else BLACK


_ortho = ((1, 0), (-1, 0), (0, 1), (0, -1))
_diag = ((1, 1), (1, -1), (-1, 1), (-1, -1))
_knight = ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1))


# --- state ---------------------------------------------------------------- #
@dataclass(frozen=True)
class Move:
    from_sq: int
    to_sq: int
    promo: str | None = None


@dataclass(frozen=True)
class State:
    board: tuple[str | None, ...]
    turn: str  # side to move
    castling: tuple[bool, bool, bool, bool] = (True, True, True, True)  # WK WQ BK BQ
    ep: int | None = None  # en-passant target square, or None
    halfmove: int = 0  # half-move clock (for 50-move draw)
    last: Move | None = None

    @property
    def is_over(self) -> bool:
        return len(legal_moves(self)) == 0


def initial_state() -> State:
    back = "RNBQKBNR"
    board: list[str | None] = [None] * 64
    for f in range(8):
        board[_idx(f, 0)] = back[f]
        board[_idx(f, 1)] = "P"
        board[_idx(f, 6)] = "p"
        board[_idx(f, 7)] = back[f].lower()
    return State(board=tuple(board), turn=WHITE)


# --- attack detection ----------------------------------------------------- #
def _attacked(board: tuple, sq: int, by_color: str) -> bool:
    """Is ``sq`` attacked by any piece of ``by_color``?"""
    f, r = _file(sq), _rank(sq)

    # pawns
    dir_ = 8 if by_color == WHITE else -8
    pawn = "P" if by_color == WHITE else "p"
    for df in (-1, 1):
        af, ar = f + df, r + (dir_ // 8)
        if _on(af, ar):
            cand = board[_idx(af, ar)]
            if cand == pawn:
                return True

    # knights
    knight = "N" if by_color == WHITE else "n"
    for df, dr in _knight:
        af, ar = f + df, r + dr
        if _on(af, ar) and board[_idx(af, ar)] == knight:
            return True

    # king
    king = "K" if by_color == WHITE else "k"
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            af, ar = f + df, r + dr
            if _on(af, ar) and board[_idx(af, ar)] == king:
                return True

    # sliding (rook/queen orthogonal, bishop/queen diagonal)
    rook = "R" if by_color == WHITE else "r"
    bishop = "B" if by_color == WHITE else "b"
    queen = "Q" if by_color == WHITE else "q"
    for df, dr in _ortho:
        af, ar = f + df, r + dr
        while _on(af, ar):
            pc = board[_idx(af, ar)]
            if pc is not None:
                if pc in (rook, queen):
                    return True
                break
            af, ar = af + df, ar + dr
    for df, dr in _diag:
        af, ar = f + df, r + dr
        while _on(af, ar):
            pc = board[_idx(af, ar)]
            if pc is not None:
                if pc in (bishop, queen):
                    return True
                break
            af, ar = af + df, ar + dr
    return False


def king_square(board: tuple, color: str) -> int | None:
    king = "K" if color == WHITE else "k"
    for i, pc in enumerate(board):
        if pc == king:
            return i
    return None


def in_check(state: State, color: str) -> bool:
    ks = king_square(state.board, color)
    if ks is None:
        return False
    return _attacked(state.board, ks, BLACK if color == WHITE else WHITE)


# --- move generation ------------------------------------------------------ #
def _board_after(state: State, move: Move) -> tuple:
    """Return the board tuple after applying ``move`` (no meta updates)."""
    board = list(state.board)
    piece = board[move.from_sq]
    if piece is None:
        return tuple(board)
    dir_ = 8 if piece == "P" else (-8 if piece == "p" else 0)
    # castling rook movement
    if piece.lower() == "k" and abs(move.to_sq - move.from_sq) == 2:
        from_file, to_file = _file(move.from_sq), _file(move.to_sq)
        rook_from = _idx(0, _rank(move.from_sq)) if to_file < from_file else _idx(7, _rank(move.from_sq))
        rook_to = _idx(3, _rank(move.from_sq)) if to_file < from_file else _idx(5, _rank(move.from_sq))
        board[rook_to] = board[rook_from]
        board[rook_from] = None
    board[move.to_sq] = move.promo or piece
    board[move.from_sq] = None
    # en passant capture
    if state.ep is not None and move.to_sq == state.ep and piece.lower() == "p" and abs(move.to_sq - move.from_sq) % 8 != 0:
        captured = move.to_sq - dir_
        board[captured] = None
    return tuple(board)


def pseudo_moves(state: State, color: str) -> list[Move]:
    board = state.board
    moves: list[Move] = []
    for idx, piece in enumerate(board):
        if piece is None or color_of(piece) != color:
            continue
        f, r = _file(idx), _rank(idx)
        low = piece.lower()

        if low == "p":
            dir_ = 8 if color == WHITE else -8
            start_rank = 1 if color == WHITE else 6
            promo_rank = 7 if color == WHITE else 0  # back rank reached = promotion
            # forward
            one = idx + dir_
            if 0 <= one < 64 and board[one] is None:
                _add_pawn(moves, idx, one, promo_rank, color)
                if r == start_rank:
                    two = idx + 2 * dir_
                    if two < 0 or two >= 64:
                        pass
                    elif board[two] is None:
                        moves.append(Move(idx, two))
            # captures
            for df in (-1, 1):
                af = f + df
                if not _on(af, r + (dir_ // 8)):  # target rank must be on board
                    continue
                target = _idx(af, r + (dir_ // 8))
                if board[target] is not None and color_of(board[target]) != color:
                    _add_pawn(moves, idx, target, promo_rank, color)
                elif state.ep is not None and target == state.ep:
                    _add_pawn(moves, idx, target, promo_rank, color)

        elif low == "n":
            for df, dr in _knight:
                af, ar = f + df, r + dr
                if _on(af, ar):
                    t = _idx(af, ar)
                    if board[t] is None or color_of(board[t]) != color:
                        moves.append(Move(idx, t))

        elif low in ("b", "r", "q"):
            dirs = _ortho if low in ("r", "q") else ()
            dirs = dirs + (_diag if low in ("b", "q") else ())
            for df, dr in dirs:
                af, ar = f + df, r + dr
                while _on(af, ar):
                    t = _idx(af, ar)
                    if board[t] is None:
                        moves.append(Move(idx, t))
                    else:
                        if color_of(board[t]) != color:
                            moves.append(Move(idx, t))
                        break
                    af, ar = af + df, ar + dr

        elif low == "k":
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    af, ar = f + df, r + dr
                    if _on(af, ar):
                        t = _idx(af, ar)
                        if board[t] is None or color_of(board[t]) != color:
                            moves.append(Move(idx, t))
            # castling
            for side in ("k", "q"):
                if not _castle_ok(state, color, idx, side):
                    continue
                moves.append(Move(idx, _idx(6 if side == "k" else 2, r)))
    return moves


def _add_pawn(moves, frm: int, to: int, promo_rank: int, color: str) -> None:
    if _rank(to) == promo_rank:
        for base in ("q", "r", "b", "n"):
            # the promo token doubles as the piece code, so case it to the mover
            moves.append(Move(frm, to, base.upper() if color == WHITE else base))
    else:
        moves.append(Move(frm, to))


def _castle_ok(state: State, color: str, king_from: int, side: str) -> bool:
    r = _rank(king_from)
    c = WHITE if color == WHITE else BLACK
    wk, wq, bk, bq = state.castling
    right = (wk if c == WHITE else bk) if side == "k" else (wq if c == WHITE else bq)
    if not right:
        return False
    if in_check(state, color):
        return False
    back = 0 if color == WHITE else 7
    king_file = _file(king_from)
    if king_file != 4 or r != back:
        return False
    empty_files = (5, 6) if side == "k" else (1, 2, 3)
    for f in empty_files:
        if state.board[_idx(f, back)] is not None:
            return False
    rook_file = 7 if side == "k" else 0
    rook = "R" if color == WHITE else "r"
    if state.board[_idx(rook_file, back)] != rook:
        return False
    pass_files = (5, 6) if side == "k" else (2, 3)  # squares the king must not pass through
    for f in pass_files:
        if _attacked(state.board, _idx(f, back), BLACK if color == WHITE else WHITE):
            return False
    return True


def legal_moves(state: State) -> list[Move]:
    """All legal moves for the side to move (moves that don't leave own king
    in check)."""
    moves: list[Move] = []
    for move in pseudo_moves(state, state.turn):
        board = _board_after(state, move)
        if not in_check(_state_with_board(state, board), state.turn):
            moves.append(move)
    return moves


def _state_with_board(state: State, board: tuple) -> State:
    return replace(state, board=board)


# --- applying a move ------------------------------------------------------ #
def apply_move(state: State, move: Move) -> State:
    if state.turn != color_of(state.board[move.from_sq]):
        raise ValueError("not that side's move")
    piece = state.board[move.from_sq]
    dir_ = 8 if piece == "P" else (-8 if piece == "p" else 0)
    board = _board_after(state, move)

    # castling rights update
    wk, wq, bk, bq = state.castling
    f, r = _file(move.from_sq), _rank(move.from_sq)
    tf, tr = _file(move.to_sq), _rank(move.to_sq)
    if piece == "K":
        wk = wq = False
    elif piece == "k":
        bk = bq = False
    if piece == "R" and f == 0 and r == 0:
        wq = False
    elif piece == "R" and f == 7 and r == 0:
        wk = False
    elif piece == "r" and f == 0 and r == 7:
        bq = False
    elif piece == "r" and f == 7 and r == 7:
        bk = False
    # a rook captured on its home square also loses the right
    victim = state.board[move.to_sq]
    if victim == "R" and tf == 0 and tr == 0:
        wq = False
    elif victim == "R" and tf == 7 and tr == 0:
        wk = False
    elif victim == "r" and tf == 0 and tr == 7:
        bq = False
    elif victim == "r" and tf == 7 and tr == 7:
        bk = False

    # en passant target (skipped square of a double pawn push)
    ep = None
    if piece.lower() == "p" and abs(move.to_sq - move.from_sq) == 16:
        ep = move.from_sq + dir_
    halfmove = 0 if piece.lower() == "p" or victim is not None or (state.ep is not None and move.to_sq == state.ep) else state.halfmove + 1

    return State(
        board=board,
        turn=BLACK if state.turn == WHITE else WHITE,
        castling=(wk, wq, bk, bq),
        ep=ep,
        halfmove=halfmove,
        last=move,
    )


# --- outcome -------------------------------------------------------------- #
def result(state: State) -> dict:
    """Full outcome for the side *about to move* (i.e. after the last move)."""
    mover = BLACK if state.turn == WHITE else WHITE  # the side that just moved
    if not any_legal(state):
        if in_check(state, state.turn):
            return {"winner": mover, "reason": "checkmate"}
        return {"winner": None, "draw": True, "reason": "stalemate"}
    if state.halfmove >= 100:
        return {"winner": None, "draw": True, "reason": "fifty_move"}
    if insufficient_material(state.board):
        return {"winner": None, "draw": True, "reason": "insufficient_material"}
    return {"winner": None, "draw": False}


def any_legal(state: State) -> bool:
    return len(legal_moves(state)) > 0


def insufficient_material(board: tuple) -> bool:
    """True only for positions that are genuinely a forced draw by material."""
    pieces = [(i, p) for i, p in enumerate(board) if p is not None and p.lower() != "k"]
    if not pieces:
        return True  # K vs K
    if len(pieces) == 1 and pieces[0][1].lower() in ("b", "n"):
        return True  # K+B vs K, K+N vs K
    # K+B vs K+B where the bishops are on the same-coloured squares
    if len(pieces) == 2 and all(p.lower() == "b" for _, p in pieces):
        c0 = color_of(pieces[0][1])
        c1 = color_of(pieces[1][1])
        if c0 != c1:  # one bishop each side
            s0 = (_file(pieces[0][0]) + _rank(pieces[0][0])) % 2
            s1 = (_file(pieces[1][0]) + _rank(pieces[1][0])) % 2
            return s0 == s1
        return False  # two bishops of the same side -> a win
    return False
