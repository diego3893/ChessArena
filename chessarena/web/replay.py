"""独立、只读的标准国际象棋PGN回放；不访问实时Game。"""

import io
import re
from pathlib import Path

import chess
import chess.pgn

MAX_BYTES = 2 * 1024 * 1024
MAX_GAMES = 100
MAX_MOVES = 10000
MAX_RECORDS = 500

# python-chess会跳过未知文本，先检查词法，避免把损坏的记录静默截短。
_TOKEN = re.compile(
    r'\s+|^%[^\n]*|\{[^}]*\}|;[^\n]*|'
    r'\[[A-Za-z0-9_]+\s+"(?:[^"\\]|\\.)*"\s*\]|'
    r'1/2-1/2|1-0|0-1|\*|\d+\.(?:\.\.)?|\$\d+|[!?]+|[()]|'
    r'(?:O-O(?:-O)?|0-0(?:-0)?|[NBKRQ]?[a-h]?[1-8]?[-x]?[a-h][1-8]'
    r'(?:=?[nbrqkNBRQK])?|--|Z0|0000|@@@@)[+#]?',
    re.MULTILINE,
)


def parse_pgn(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("请选择非空的PGN文件")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("PGN文件不能超过2MiB")
    text = text.lstrip("\ufeff")
    position = depth = 0
    for token in _TOKEN.finditer(text):
        if token.start() != position:
            raise ValueError("PGN含有无法识别的内容：" + text[position:position + 32])
        position = token.end()
        if token.group() == "(":
            depth += 1
        elif token.group() == ")":
            depth -= 1
        if not 0 <= depth <= 64:
            raise ValueError("PGN变例括号不匹配或嵌套过深")
    if position != len(text) or depth:
        raise ValueError("PGN格式不完整或含有无法识别的内容")

    move_count = 0

    class CheckedBuilder(chess.pgn.GameBuilder):
        def handle_error(self, error):
            raise ValueError("PGN解析失败：" + str(error)) from error

        def visit_move(self, board, move):
            nonlocal move_count
            move_count += 1
            if move_count > MAX_MOVES:
                raise ValueError("PGN总着法数不能超过10000（含变例）")
            if not board.is_valid() or not board.is_legal(move):
                raise ValueError("PGN包含非法局面或着法：" + move.uci())
            super().visit_move(board, move)

    stream = io.StringIO(text)
    games = []
    while True:
        try:
            game = chess.pgn.read_game(stream, Visitor=CheckedBuilder)
        except (ValueError, IndexError) as exc:
            raise ValueError(str(exc)) from exc
        if game is None:
            break
        if len(games) >= MAX_GAMES:
            raise ValueError("PGN最多包含100盘对局")
        if game.headers.get("Variant", "Standard").lower() not in {"standard", "chess", "normal"}:
            raise ValueError("播放器仅支持标准国际象棋PGN")
        board = game.board()
        if not board.is_valid():
            raise ValueError("PGN的初始FEN不是合法局面")
        result = game.headers.get("Result", "*")
        if result not in {"1-0", "0-1", "1/2-1/2", "*"}:
            raise ValueError("PGN的Result标签无效")
        captured = {"w": [], "b": []}

        def frame(last_move=None):
            return {
                "fen": board.fen(en_passant="fen"),
                "turn": "w" if board.turn else "b",
                "is_check": board.is_check(),
                "last_move": last_move,
                "captured": {side: pieces.copy() for side, pieces in captured.items()},
            }

        frames, moves = [frame()], []
        for move in game.mainline_moves():
            moves.append({"uci": move.uci(), "san": board.san(move),
                          "side": "w" if board.turn else "b", "fullmove_number": board.fullmove_number})
            if board.is_capture(move):
                square = (chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
                          if board.is_en_passant(move) else move.to_square)
                victim = board.piece_at(square)
                captured["w" if victim.color else "b"].append(victim.symbol())
            board.push(move)
            frames.append(frame(move.uci()))
        games.append({"headers": dict(game.headers), "result": result, "moves": moves,
                      "frames": frames, "pgn": str(game)})
    if not games:
        raise ValueError("文件中没有PGN对局")
    return {"games": games}


class RecordStore:
    """只允许读取指定目录中的PGN，路径解析后再次检查目录边界。"""

    def __init__(self, roots):
        self.roots = {name: Path(path).resolve() for name, path in roots.items()}

    def _path(self, record_id):
        if not isinstance(record_id, str) or "\\" in record_id:
            raise ValueError("无效的记录路径")
        name, separator, relative = record_id.partition("/")
        if not separator or name not in self.roots:
            raise ValueError("记录必须位于runs/或results/目录")
        root = self.roots[name]
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() != ".pgn":
            raise ValueError("无效的PGN记录路径")
        return path

    def list(self):
        records = []
        for name, root in self.roots.items():
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() != ".pgn":
                    continue
                record_id = name + "/" + path.relative_to(root).as_posix()
                try:
                    resolved = self._path(record_id)
                    if not resolved.is_file():
                        continue
                    stat = resolved.stat()
                    records.append({"id": record_id, "size": stat.st_size, "modified": stat.st_mtime})
                except (ValueError, OSError):
                    continue
        records.sort(key=lambda record: (-record["modified"], record["id"]))
        return {"records": records[:MAX_RECORDS]}

    def read(self, record_id):
        path = self._path(record_id)
        try:
            with path.open("rb") as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError as exc:
            raise ValueError("记录不存在或无法读取") from exc
        if len(data) > MAX_BYTES:
            raise ValueError("PGN文件不能超过2MiB")
        try:
            return data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("PGN文件必须使用UTF-8编码") from exc
