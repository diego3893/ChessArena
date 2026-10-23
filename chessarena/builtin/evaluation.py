"""内置 AI 共用的评估函数：子力 + 兵的推进奖励。

刻意保持简单（约 40 行）：学生要能一眼看懂、也敢改。
"""

import chess

#: 子力价值（分）
VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

MATE = 100000

_CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}


def _position_bonus(square: int, piece: chess.Piece) -> int:
    """极简位置奖励：马/象别缩在边线，兵占中心略加分。"""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        if file in (0, 7):
            return -8
        if 2 <= file <= 5 and 2 <= rank <= 5:
            return 6
        return 0
    if piece.piece_type == chess.PAWN and square in _CENTER:
        return 10
    return 0


def evaluate(board: chess.Board) -> int:
    """白方视角的静态分：正数=白好，负数=黑好。"""
    if board.is_checkmate():
        return -MATE if board.turn else MATE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    total = 0
    for square, piece in board.piece_map().items():
        score = VALUE[piece.piece_type] + _position_bonus(square, piece)
        if piece.piece_type == chess.PAWN:
            rank = chess.square_rank(square)
            # 越靠近升变越值钱（白方 rank 越大越好，黑方相反）
            score += 8 * (rank if piece.color else 7 - rank)
        total += score if piece.color else -score
    return total


def value_of(piece: chess.Piece | None) -> int:
    """单子价值，用于着法排序（MVV-LVA）。"""
    return VALUE[piece.piece_type] if piece is not None else 0
