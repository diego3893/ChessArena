"""学生可见的不可变局面数据；不包含着法生成、动作掩码或推演接口。"""

from dataclasses import dataclass

import chess


@dataclass(frozen=True, slots=True, init=False)
class State:
    fen: str
    board: tuple[tuple[str, ...], ...]
    turn: str
    castling_rights: str
    ep_square: str | None
    halfmove_clock: int
    fullmove_number: int
    history: tuple[str, ...]
    start_fen: str
    game_id: str | None
    last_error: str | None
    is_check: bool
    is_game_over: bool
    result: str | None
    over_reason: str | None

    def __init__(self, board, history=(), last_error=None, *, result=None,
                 start_fen=None, game_id=None, over_reason=None, over=None):
        fen = board.fen(en_passant="fen")
        fields = fen.split()
        if over is None:
            outcome = board.outcome(claim_draw=False)
            result = result or (outcome.result() if outcome else None)
            if result is None and (board.is_repetition(3) or board.is_fifty_moves()):
                result = "1/2-1/2"
            over = result is not None
        values = {
            "fen": fen,
            "board": tuple(tuple(
                p.symbol() if (p := board.piece_at(chess.square(f, r))) else "."
                for f in range(8)) for r in range(7, -1, -1)),
            "turn": fields[1], "castling_rights": fields[2],
            "ep_square": None if fields[3] == "-" else fields[3],
            "halfmove_clock": int(fields[4]), "fullmove_number": int(fields[5]),
            "history": tuple(history), "start_fen": start_fen or fen,
            "game_id": game_id, "last_error": last_error,
            "is_check": board.is_check(), "is_game_over": bool(over),
            "result": result, "over_reason": over_reason,
        }
        for key, value in values.items():
            object.__setattr__(self, key, value)

    @property
    def ply(self):
        return len(self.history)

    def copy(self):
        return self

    def pretty(self):
        return "\n".join(" ".join(row) for row in self.board) + "\nFEN: " + self.fen

    def to_json(self):
        return {
            "fen": self.fen, "board": [list(row) for row in self.board],
            "turn": self.turn, "castling_rights": self.castling_rights,
            "ep_square": self.ep_square, "halfmove_clock": self.halfmove_clock,
            "fullmove_number": self.fullmove_number, "history": list(self.history),
            "start_fen": self.start_fen, "game_id": self.game_id,
            "ply": self.ply, "last_error": self.last_error,
            "is_check": self.is_check, "over": self.is_game_over,
            "result": self.result, "over_reason": self.over_reason,
        }

    @classmethod
    def from_json(cls, data):
        return cls(chess.Board(data["fen"]), data.get("history", ()),
                   data.get("last_error"), result=data.get("result"),
                   start_fen=data.get("start_fen"), game_id=data.get("game_id"),
                   over_reason=data.get("over_reason"), over=data.get("over", False))
