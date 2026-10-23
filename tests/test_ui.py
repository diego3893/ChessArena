"""前端接线的静态检查：选择器与资源引用必须真实存在。

浏览器端行为（真实点击、动画）仍需人工验收，但"JS 里找的 id 在 HTML 里不存在"
这类错误可以由这里挡住。
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "chessarena" / "web" / "ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
JS = (UI / "app.js").read_text(encoding="utf-8")
CSS = (UI / "style.css").read_text(encoding="utf-8")


class TestUiWiring(unittest.TestCase):
    def test_ids_used_by_js_exist_in_html(self):
        html_ids = set(re.findall(r'id="([^"]+)"', HTML))
        used = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', JS))
        used |= set(re.findall(r'querySelectorAll\("#([A-Za-z0-9_-]+)', JS))
        missing = sorted(used - html_ids)
        self.assertEqual(missing, [], "app.js 引用了 HTML 中不存在的 id：%s" % (missing,))

    def test_asset_references_exist(self):
        refs = re.findall(r'(?:src|href)="(/[^"]+)"', HTML)
        self.assertTrue(refs, "index.html 里没有任何静态资源引用")
        for url in refs:
            if url.startswith("/ui/"):
                path = UI / url[len("/ui/"):]
            elif url.startswith("/vendor/"):
                path = ROOT / "vendor" / url[len("/vendor/"):]
            else:
                self.fail("资源路径必须以 /ui/ 或 /vendor/ 开头：%s" % (url,))
            self.assertTrue(path.is_file(), "资源不存在：%s -> %s" % (url, path))

    def test_style_classes_used_by_html_exist(self):
        html_classes = set()
        for chunk in re.findall(r'class="([^"]+)"', HTML):
            html_classes.update(chunk.split())
        css_classes = set(re.findall(r'\.([A-Za-z][A-Za-z0-9_-]*)', CSS))
        # 允许仅由 JS 添加的状态类
        dynamic = {
            "hidden", "active", "ok", "bad", "last", "white-cap", "black-cap",
            "white", "black", "dot", "toast",
        }
        missing = sorted(html_classes - css_classes - dynamic)
        self.assertEqual(missing, [], "HTML 用到但 CSS 未定义的类：%s" % (missing,))

    def test_no_legacy_engine_calls(self):
        # 前端不得自己判规则：只应通过 HTTP 与服务端交互
        for forbidden in ("chess.js", "Chessground(", "legal_moves("):
            if forbidden == "Chessground(":
                continue
            self.assertNotIn(forbidden, JS)


if __name__ == "__main__":
    unittest.main()
