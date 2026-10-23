"""FastAPI 服务：HTTP 3 端点 + WebSocket 推送（协议见《API总表》§16）。"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse

from .. import __version__
from ..web.session import Session

_STATUS = {0: 200, -1: 400, -2: 400, -3: 409, -4: 410}
_SENTINEL = object()


def _envelope(result, session):
    return {
        "result": {
            "ok": bool(result.ok),
            "code": int(result.code),
            "reason": result.reason,
            "move": result.move,
        },
        "state": session.snapshot(),
    }


def create_app(session: Session) -> FastAPI:
    """把一局 ``Session`` 包成 ASGI 应用。"""

    @asynccontextmanager
    async def lifespan(app):
        session.hub.loop = asyncio.get_running_loop()
        try:
            yield
        finally:
            session.hub.loop = None

    app = FastAPI(title="ChessArena", version=__version__, lifespan=lifespan)
    app.state.session = session

    # --- 读 -----------------------------------------------------------
    @app.get("/")
    def index():
        return {"name": "ChessArena", "version": __version__, "state": session.snapshot()}

    @app.get("/state")
    def get_state():
        return session.snapshot()

    @app.get("/legal_moves")
    def get_legal_moves():
        state = session.snapshot()
        return {"turn": state["turn"], "legal_moves": state["legal_moves"]}

    @app.get("/pgn")
    def get_pgn():
        return PlainTextResponse(session.game.pgn())

    # --- 写 -----------------------------------------------------------
    @app.post("/move")
    def post_move(payload: dict = Body(default=None)):
        result = session.submit((payload or {}).get("move"))
        return JSONResponse(_envelope(result, session), status_code=_STATUS.get(result.code, 500))

    @app.post("/reset")
    def post_reset(payload: dict = Body(default=None)):
        result = session.reset((payload or {}).get("fen"))
        return JSONResponse(_envelope(result, session), status_code=_STATUS.get(result.code, 500))

    @app.post("/control")
    def post_control(payload: dict = Body(default=None)):
        body = payload or {}
        try:
            message = session.control(body.get("action"), body.get("speed"))
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(message)

    # --- WebSocket -----------------------------------------------------
    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        queue: asyncio.Queue = asyncio.Queue()
        session.hub.register(queue)
        await sock.send_json({"type": "hello", "state": session.snapshot()})
        sender = asyncio.create_task(_send_loop(sock, queue))
        reader = asyncio.create_task(_read_loop(sock, queue))
        try:
            await asyncio.wait({sender, reader}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (sender, reader):
                task.cancel()
            session.hub.unregister(queue)

    return app


async def _send_loop(sock: WebSocket, queue: "asyncio.Queue"):
    while True:
        message = await queue.get()
        if message is _SENTINEL:
            return
        await sock.send_json(message)


async def _read_loop(sock: WebSocket, queue: "asyncio.Queue"):
    """只处理 ping；落子一律走 HTTP，保证"单写入口"只有一条路径。"""
    try:
        while True:
            data = await sock.receive_json()
            if isinstance(data, dict) and data.get("type") == "ping":
                queue.put_nowait({"type": "pong"})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        return
    finally:
        queue.put_nowait(_SENTINEL)


def serve(session: Session, *, host="127.0.0.1", port=8000):
    """阻塞式启动（CLI 用）。"""
    import uvicorn

    app = create_app(session)
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    finally:
        session.stop()
