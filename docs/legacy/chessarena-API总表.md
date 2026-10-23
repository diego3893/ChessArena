# ChessArena API总表

本表对应学生接口v2。旧legal_moves、moves_from和State.apply接口已从学生数据、Client、HTTP和WebSocket中移除。

## 1 对象

| 对象 | 职责 |
|---|---|
| Arena | 助教/训练脚本装配环境、创建比赛、加载选手 |
| Game | 裁判和管理对象；唯一执行真实棋盘修改的组件 |
| State | 不可变局面数据，无动作生成、推演或动作掩码 |
| Board | 只读棋子视图，无规则引擎引用 |
| Player | 注入学生Agent的受限接口，绑定执棋颜色 |
| Agent | 学生程序生命周期，choose_move(state)返回UCI或主动submit的Result |
| TorchAgent | 可选PyTorch生命周期适配，不限定编码或网络形状 |
| Client | 同进程接口的HTTP对应实现 |

State字段、Player方法和模型钩子详见[学生API](chessarena-学生API.md)。模型文件组织见[提交规范](chessarena-模型提交规范.md)。

## 2 裁判和控制

Game.submit(move, strict=False)唯一提交真实着法。返回具有ok/code/reason/move属性的Result，错误码0/-1/-2/-3/-4分别为成功/非法/格式错/越轮/终局。失败不改变棋子、轮次和历史；允许更新last_error与拒绝记录。

Game提供state、board、turn、history、ply、result、over、over_reason、last_error。player(side)返回绑定颜色的Player。训练管理端可调用reset(fen)、undo(n)、resign(side)、step()、run_to_end(max_plies=1000)、pgn()、on(event, callback)和clock(side)。学生不接收Game对象。

事件名为move、illegal、opponent_move、game_over、timeout、retry。所有动作，包括学生主动submit、平台代理返回的UCI、人类点击、UCI引擎及HTTP服务返回的动作，均交给同一裁判。

## 3 HTTP接口

| 方法 | 路径 | 输入/响应 |
|---|---|---|
| GET | /state | 完整只读局面及UI会话字段 |
| POST | /move | {"move":"e2e4","side":"w"}；返回{"result":{...},"state":{...}} |
| POST | /reset | 可选{"fen":"..."}，本机训练管理接口 |
| POST | /control | action为pause/resume/step/speed/undo/resign/new；new可传white/black |
| GET | /players | {"human":true,"api":true,"builtin":[...],"agents":[...]} |
| GET | /pgn | text/plain的PGN |
| GET | /debug | 驱动状态、步数、停滞数和最近异常 |
| WS | /ws | 初始hello，随后move/game_over/reset/control/heartbeat等推送 |

GET /legal_moves已删除，返回404。所有快照以及POST /move拒绝响应均无候选动作、合法落点或动作掩码。

HTTP状态码为0→200，-1/-2→400，-3→409，-4→410；响应中的result始终含ok/code/reason/move。POST /control参数错误返回400和error。

API方必须指定side=w或b，越轮、遗漏颜色、暂停或服务端AI回合返回-3；格式错误的side返回-2。人类方可省略side。side是本机协议约定，不是身份认证。旧的本机reset/control管理入口保留，不提供多用户权限隔离。

## 4 快照

State提供fen、board、turn、castling_rights、ep_square、halfmove_clock、fullmove_number、start_fen、history、ply、game_id、is_check、is_game_over、result、over_reason、last_error。JSON用over表示is_game_over；board和history序列化为数组。fen保留原始吃过路兵目标格，包括当前没有可吃过路兵棋子的情况。

HTTP/UI补充history_san、captured、last_move、white、black、human、api、players、paused、speed、timeout和revision。revision在会话内递增；客户端不按ply判断新旧，以便正确处理悔棋和重置。captured.w/b分别表示白/黑吃掉的棋子符号列表。

WebSocket连接先发{"type":"hello","version":"...","state":{...}}。move带move/ply/state；game_over带result/reason/state；reset/control/heartbeat带state；illegal/retry仅带拒绝码和原因，不含合法替代动作。客户端只发ping，服务端回pong；落子统一走POST /move。

浏览器chessground允许提出动作，由裁判决定是否生效；不展示平台合法落点。升变选择只是用户输入，不意味着动作已被判合法。

## 5 学生及外部选手

选手标识支持human、api、builtin:random/greedy/minimax2/minimax3/stockfish、agents/A.py、uci:名字、http:名字。

agents/agents.json是列表：UCI项含name/type="uci"/cmd/options/timeout；HTTP项含name/type="http"/url/timeout。扫描失败记录在Arena.agent_errors，其他可用选手仍展示。

UCI按uci/isready/position fen/go/bestmove交互。HTTP服务收到State.to_json()数据，自己生成动作并返回{"move":"e2e4"}。网络失败和运行中引擎退出使用TransientError进入重试；配置/启动错误使用EngineError判负。

## 6 时间与运行

默认每步3秒，初次加3次重试共享预算；选手可返回UCI，或返回self.game.submit(move)的Result。成功提交不重复执行；失败的Result触发下一次choose_move。超时思考请求被取消，不能在其后回合补交动作。

TorchAgent在on_game_start加载并预热，推理只调用学生encode/predict/decode，不提供平台编码器、动作编号或合法动作筛选。基础平台不导入torch；神经网络模式需requirements-pytorch.txt。

无头训练和现场比赛均使用State/Player契约。内置基线同样接收State，在各自实现中自行使用规则库生成动作。Python同进程插件是可信代码，接口收窄不构成针对反射或私有模块导入的安全沙箱。

CLI提供serve、play、test、league、replay；配置含server/game/league/stockfish，详见[README](../README.md)。
