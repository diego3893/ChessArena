"""注入学生Agent的受限接口：只读局面、提交动作和认输。"""

import time

from .board import Board


class Player:
    __slots__ = ("__read", "__submit", "__resign", "__clock", "color")

    def __init__(self, color, read, submit, resign, clock):
        self.color = color
        self.__read = read
        self.__submit = submit
        self.__resign = resign
        self.__clock = clock

    @property
    def state(self):
        return self.__read()

    @property
    def board(self):
        return Board._live(self.__read)

    @property
    def turn(self):
        return self.state.turn

    @property
    def over(self):
        return self.state.is_game_over

    @property
    def result(self):
        return self.state.result

    @property
    def history(self):
        return self.state.history

    @property
    def ply(self):
        return self.state.ply

    @property
    def last_error(self):
        return self.state.last_error

    @property
    def game_id(self):
        return self.state.game_id

    def submit(self, move, *, strict=False):
        return self.__submit(move, strict=strict)

    def resign(self):
        return self.__resign()

    def clock(self):
        return self.__clock()

    def wait_my_turn(self, *, timeout=10.0):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            state = self.state
            if state.is_game_over:
                return False
            if state.turn == self.color:
                return True
            time.sleep(0.01)
        return False
