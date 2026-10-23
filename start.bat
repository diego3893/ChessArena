@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ChessArena] 找不到 python，请先安装 Python 3.10+ 并勾选 "Add to PATH"。
  pause
  exit /b 1
)

python -c "import chess, fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo [ChessArena] 首次运行，安装依赖 ...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ChessArena] 依赖安装失败，请检查网络或 pip 配置。
    pause
    exit /b 1
  )
)

echo [ChessArena] 正在启动，浏览器会自动打开 http://127.0.0.1:8000/
start "" "http://127.0.0.1:8000/"
python -m chessarena serve

echo.
echo [ChessArena] 已退出。
pause
