"""FastAPI 服务：HTTP 3 端点 + WebSocket 推送（协议见《API总表》§16）。"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..web.session import Session

_STATUS = {0: 200, -1: 400, -2: 400, -3: 409, -4: 410}
_SENTINEL = object()
UI_DIR = Path(__file__).resolve().parent / "ui"
ROOT_DIR = Path(__file__).resolve().parents[2]
VENDOR_DIR = ROOT_DIR / "vendor"
_NO_CACHE = {"Cache-Control": "no-store"}



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
        maintenance = asyncio.create_task(_maintain(session))
        try:
            yield
        finally:
            maintenance.cancel()
            session.hub.loop = None

    app = FastAPI(title="ChessArena", version=__version__, lifespan=lifespan)
    app.state.session = session

    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")
    if VENDOR_DIR.is_dir():
        app.mount("/vendor", StaticFiles(directory=str(VENDOR_DIR)), name="vendor")

    # --- 页面 ---------------------------------------------------------
    @app.get("/")
    def index():
        page = UI_DIR / "index.html"
        if page.is_file():
            return FileResponse(page, headers=_NO_CACHE)
        return JSONResponse({
            "name": "ChessArena",
            "version": __version__,
            "hint": "前端页面尚未构建（web/ui/ 不存在）",
            "state": session.snapshot(),
        })

    # --- 读 -----------------------------------------------------------
    @app.get("/state")
    def get_state():
        return JSONResponse(session.snapshot(), headers=_NO_CACHE)

    @app.get("/debug")
    def get_debug():
        """诊断用：驱动线程是否活着、卡了几次、有几个 WS 客户端。"""
        return JSONResponse(session.debug(), headers=_NO_CACHE)

    @app.get("/players")
    def get_players():
        """页面下拉框用：可选的人类 / 内置档 / 已加载的外部对手。"""
        return JSONResponse(session.available_players(), headers=_NO_CACHE)

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
            message = session.control(
                body.get("action"),
                body.get("speed"),
                body.get("white"),
                body.get("black"),
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(message)

    # --- WebSocket -----------------------------------------------------
    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        queue: asyncio.Queue = asyncio.Queue()
        session.hub.register(queue)
        await sock.send_json({"type": "hello", "version": __version__, "state": session.snapshot()})
        sender = asyncio.create_task(_send_loop(sock, queue))
        reader = asyncio.create_task(_read_loop(sock, queue))
        beat = asyncio.create_task(_heartbeat(session, queue))
        try:
            await asyncio.wait({sender, reader, beat}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (sender, reader, beat):
                task.cancel()
            session.hub.unregister(queue)

    return app


async def _send_loop(sock: WebSocket, queue: "asyncio.Queue"):
    while True:
        message = await queue.get()
        if message is _SENTINEL:
            return
        await sock.send_json(message)


async def _heartbeat(session: Session, queue: "asyncio.Queue"):
    """每 N 秒推一份完整快照：即使漏了某条 move 消息，页面也会被纠正回来。"""
    while True:
        await asyncio.sleep(max(0.2, session.heartbeat))
        queue.put_nowait({"type": "heartbeat", "state": session.snapshot()})


async def _maintain(session: Session):
    """后台自愈：驱动线程意外退出就重启。"""
    while True:
        await asyncio.sleep(2.0)
        try:
            session.ensure_driver()
        except Exception as exc:  # 自愈失败也不能拖垮服务
            print("[chessarena] ensure_driver 失败：%r" % (exc,), flush=True)


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
