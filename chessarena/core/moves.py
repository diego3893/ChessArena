"""坐标、着法字符串与校验。

着法格式只有一个：UCI 字符串（小写起终点，升变加子），例如 ``e2e4``、``e7e8q``。
这里不做任何"猜测式纠错"：``Nf3``、``E2E4``、``e2-e4`` 一律判为格式错误（``-2``）。
"""

FILES = "abcdefgh"
RANKS = "12345678"
PROMO = "qrbn"


def square(x: int, y: int) -> str:
    """``(4, 1) -> "e2"``；``x`` 列 0–7，``y`` 行 0–7（从下往上）。"""
    if not (0 <= x <= 7 and 0 <= y <= 7):
        raise ValueError("坐标越界：x=%r, y=%r（应在 0..7）" % (x, y))
    return FILES[x] + RANKS[y]


def xy(sq: str) -> tuple[int, int]:
    """``"e2" -> (4, 1)``。"""
    if not isinstance(sq, str) or len(sq) != 2 or sq[0] not in FILES or sq[1] not in RANKS:
        raise ValueError("格名不合法：%r（应形如 e2）" % (sq,))
    return FILES.index(sq[0]), RANKS.index(sq[1])


def uci(x1: int, y1: int, x2: int, y2: int, promo: str = "") -> str:
    """坐标转着法串。``promo`` 只接受 ``"q"/"r"/"b"/"n"``（可省）。"""
    if promo and (not isinstance(promo, str) or promo not in PROMO):
        raise ValueError("升变子不合法：%r（只能是 q / r / b / n）" % (promo,))
    return square(x1, y1) + square(x2, y2) + promo


def parse_uci(move) -> tuple[str, str, str] | None:
    """校验格式；合法返回 ``(from_sq, to_sq, promo)``，否则返回 ``None``。

    注意：这里只管"像不像着法"，不管"这步棋走不走得通"——后者是 ``-1``。
    """
    if not isinstance(move, str):
        return None
    if len(move) not in (4, 5):
        return None
    if move[0] not in FILES or move[1] not in RANKS:
        return None
    if move[2] not in FILES or move[3] not in RANKS:
        return None
    if len(move) == 5 and move[4] not in PROMO:
        return None
    return move[0:2], move[2:4], move[4:5]
