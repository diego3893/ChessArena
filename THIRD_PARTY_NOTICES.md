# 第三方版权与许可证

ChessArena平台代码采用GNU General Public License第3版或任何后续版本（`GPL-3.0-or-later`），全文见[LICENSE](LICENSE)。原创代码版权归各自贡献者所有；第三方代码、资源和二进制保留其原作者版权及原有许可声明。本项目按许可证原样提供，不附带担保。

## Stockfish19

- 文件：`thirdparty/stockfish-windows-x86-64-universal.exe`，来自未经修改的官方Windows x86-64 universal发布包。
- 版权：Copyright (C) 2004–2026 The Stockfish developers。Stockfish源自Glaurung2.1。
- 许可：`GPL-3.0-or-later`，见[原始许可证](thirdparty/licenses/stockfish/Copying.txt)及[原始作者名单](thirdparty/licenses/stockfish/AUTHORS)。
- 保留的[上游README](thirdparty/licenses/stockfish/README.upstream.md)包含许可、网络训练数据来源和致谢。
- 对应源码、固定提交、构建脚本、NNUE下载地址及二进制校验值见[第三方分发说明](thirdparty/README.md)。

## chessground10.5.0

- 文件：`vendor/chessground/`中的JavaScript、CSS和包元数据，来自`@lichess-org/chessground`10.5.0官方npm包。
- 作者：Lichess Team及上游贡献者。保留各文件中的版权和资源归属声明。
- 许可：`GPL-3.0-or-later`，见[原始许可证](vendor/chessground/LICENSE)。
- 对应TypeScript源码、构建配置和依赖锁文件随仓库提供，见[第三方分发说明](thirdparty/README.md)。

`chessground.cburnett.css`内嵌棋子采用Cburnett（ColinM.L.Burnett）的设计，经上游整理并嵌入CSS；本项目未修改这些运行资源。原始作品及多重许可声明见[WikimediaCommons棋子文件](https://commons.wikimedia.org/wiki/File:Chess_plt45.svg)及其同系列文件；其中允许GPL第2版或后续版本，本分发选择GPL第3版或后续版本，全文见[LICENSE](LICENSE)。原作者及后续贡献者版权保留。

## 安装依赖

python-chess（PyPI包名`chess`）采用`GPL-3.0-or-later`，版权归NiklasFiekas及上游贡献者，见[上游源码与许可](https://github.com/niklasf/python-chess)。本项目通过`requirements.txt`安装该库。

FastAPI、Uvicorn、PyYAML、websockets以及可选PyTorch等依赖保留各自许可证；依赖版本由实际安装环境决定。重新打包分发这些依赖时，应同时保留相应版本的许可证与版权声明。学生提交的模型、数据和代码应附带各自适用的许可及来源说明。

## 再分发

分发本平台或其中第三方程序时，请保留许可证、版权声明和对应源码获取说明；随二进制提供本仓库中的对应源码归档。修改GPL代码后再分发时，也须按GPL提供相应修改源码。替换Stockfish或chessground版本时，应同步更新源码、许可证和校验值，不能继续使用旧版本的源码说明。
