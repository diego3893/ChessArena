# chessground（预构建产物）

本目录是 **@lichess-org/chessground v10.5.0 官方 npm 包**里的构建产物，原样 vendor 进来，供页面以
`<script type="module">` 直接引用，**不需要任何构建步骤**（决定见 `PROJECT_CONTEXT.md` D006 / D007）。

| 文件 | 说明 |
|---|---|
| `dist/chessground.min.js` | 单文件 ESM（33,291 B），导出 `Chessground` |
| `assets/chessground.base.css` | 棋盘几何 + 基础样式（必需） |
| `assets/chessground.brown.css` | 木质配色（可选） |
| `assets/chessground.cburnett.css` | cburnett 棋具样式（可选） |
| `LICENSE` | GPL-3.0 全文（35,147 B） |
| `package.json` | 上游元数据（版本 / 许可证 / 依赖，均无运行时依赖） |

## 来源与校验

- 来源：`npm pack @lichess-org/chessground` → `lichess-org-chessground-10.5.0.tgz`
- `dist/chessground.min.js` SHA256：`CCC1AAF2389A7FACA68C47E1DF24B91976DAD208FDD005100E655CB0EF70A591`
- 一致性检查：文件含 `export {` 与 `Chessground`，不含 `sourceMappingURL`。
- 对应源码：<https://github.com/lichess-org/chessground>（本仓库 `thirdparty/chessground/` 有克隆副本）

## 许可证

GPL-3.0-or-later。引入本目录会使前端受 GPL 约束：向使用者分发页面时须同时提供对应源码。
校内教学与公开课程仓库已确认可接受（`PROJECT_CONTEXT.md` D014）。
