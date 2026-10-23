# 第三方程序分发说明

本目录随仓库分发Stockfish官方exe、对应版本源码归档及许可证。`stockfish/`、`chessground/`本地解压或克隆目录与原始下载ZIP被忽略，不影响以下文件进入Git。

## Stockfish19

| 项目 | 内容 |
|---|---|
| 二进制 | [stockfish-windows-x86-64-universal.exe](stockfish-windows-x86-64-universal.exe) |
| 文件大小 | 103046300字节，约98.3MiB |
| 上游版本 | [sf_19官方发布](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19) |
| 对应提交 | `edb0d9db6731067ec50ce619ff372b463bc4dd5d` |
| 许可证 | [GPLv3全文](licenses/stockfish/Copying.txt)，上游源文件允许第3版或后续版本 |
| 作者 | [原始AUTHORS](licenses/stockfish/AUTHORS) |
| 上游说明 | [原始README](licenses/stockfish/README.upstream.md) |
| 对应源码 | [随仓库提供的源码归档](stockfish-source-sf_19.tar.gz)，包含`src/`、Makefile、`scripts/`及`.github/`构建工作流 |

exe未作修改。原始下载为[官方Windows发布ZIP](https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip)，其SHA256为：

```text
3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7
```

该值与官方GitHub发布资产元数据一致；本仓库exe与该ZIP中exe的SHA256一致。随仓库提供的源码归档来自[固定提交源码下载](https://codeload.github.com/official-stockfish/Stockfish/tar.gz/edb0d9db6731067ec50ce619ff372b463bc4dd5d)，也可[在线浏览对应源码](https://github.com/official-stockfish/Stockfish/tree/edb0d9db6731067ec50ce619ff372b463bc4dd5d)。

### 构建与NNUE

解压源码后，`src/Makefile`和`.github/workflows/universal_compilation.yml`中的`UniversalWindows`任务记录构建流程：MSYS2/MinGW64、GCC、make、IntelSDE9.58.0，以及`ARCH=x86-64-universal profile-build`、SDE运行前缀、strip等参数。请依照该固定版本的工作流构建；本仓库未重新编译exe，也未验证本机逐字节复现。

官方exe内嵌`nn-1a298aa575a0.nnue`。源码中的`scripts/net.sh`提供下载与文件名哈希校验，可在构建时获取同一网络文件，下载地址如下：

- [Stockfish官方网络下载](https://tests.stockfishchess.org/api/nn/nn-1a298aa575a0.nnue)
- [官方networks仓库镜像](https://github.com/official-stockfish/networks/raw/master/nn-1a298aa575a0.nnue)

NNUE文件未在本仓库另外复制；不需要将它解压到exe旁才能运行。上游README中关于LeelaChessZero训练数据及ODbL的致谢已原样保留。

## chessground10.5.0

`vendor/chessground/`中的运行文件与[官方npm10.5.0发布包](https://registry.npmjs.org/@lichess-org/chessground/-/chessground-10.5.0.tgz)逐字节一致。作者及许可见[第三方版权声明](../THIRD_PARTY_NOTICES.md)和[原始LICENSE](../vendor/chessground/LICENSE)。

- 对应源码：[随仓库提供的源码归档](chessground-source-10.5.0.tar.gz)。
- 上游版本：`v10.5.0`，提交`b4f605018e1043640c917e82a74b214cb58e4a05`。
- 在线获取：[固定提交源码下载](https://codeload.github.com/lichess-org/chessground/tar.gz/b4f605018e1043640c917e82a74b214cb58e4a05)。
- 归档包括`src/`、资源、`package.json`、`tsconfig.json`和`pnpm-lock.yaml`。构建环境及命令见其中的`engines`与`scripts`（安装锁定依赖后运行`pnpm run dist`）。使用已附带的运行文件时无需构建。

## 校验与更新

本仓库分发文件的SHA256见[SHA256SUMS](SHA256SUMS)。PowerShell可使用`Get-FileHash -Algorithm SHA256 <文件路径>`核对。更新exe时同步替换对应源码归档、上游许可/作者名单与本文版本信息，并重新生成校验值。

上传GitHub时，exe可通过Git提交和推送；其大小低于100MiB单文件限制，超过50MiB会收到提示。网页上传仅支持25MiB，不能用于此exe。限制见[GitHub官方文档](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。
