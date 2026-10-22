"""返回码常量。

``submit()`` 的所有结果都用这套数字表达；学生可以直接 ``r == -1`` 比较。
"""


class RC:
    """返回码枚举（与《API总表》§5 一一对应）。"""

    OK = 0
    ILLEGAL_MOVE = -1
    BAD_FORMAT = -2
    NOT_YOUR_TURN = -3
    GAME_OVER = -4

    NAMES = {
        OK: "OK",
        ILLEGAL_MOVE: "ILLEGAL_MOVE",
        BAD_FORMAT: "BAD_FORMAT",
        NOT_YOUR_TURN: "NOT_YOUR_TURN",
        GAME_OVER: "GAME_OVER",
    }

    @classmethod
    def name(cls, code):
        """返回码的常量名；未知码回退成字符串。"""
        return cls.NAMES.get(code, "UNKNOWN(%r)" % (code,))
