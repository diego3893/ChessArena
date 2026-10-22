"""``Result``：``submit()`` 的返回值。

设计要点：既能当布尔用（``if r:``），也能直接和返回码比较（``r == -1``），
所以学生不需要记住任何属性名就能写出可运行的代码。
"""

from dataclasses import dataclass

from .rc import RC


@dataclass(frozen=True, slots=True)
class Result:
    """一次落子尝试的结果（只读）。"""

    code: int
    reason: str = ""
    move: str | None = None

    @property
    def ok(self) -> bool:
        """``True`` 表示落子成功（``code == 0``）。"""
        return self.code == RC.OK

    def __bool__(self) -> bool:
        return self.code == RC.OK

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            return self.code == other
        if isinstance(other, Result):
            return (self.code, self.move) == (other.code, other.move)
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.code, self.move))

    def __str__(self) -> str:
        tag = RC.name(self.code)
        if self.ok:
            return "OK %s" % (self.move or "")
        return "%s(%d): %s" % (tag, self.code, self.reason)

    def __repr__(self) -> str:
        return "Result(code=%d, move=%r, reason=%r)" % (self.code, self.move, self.reason)


OK = Result(RC.OK)
