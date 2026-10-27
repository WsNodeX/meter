"""report 模块测试：面板生成与转义安全。"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from meter.report import render
from meter.store import CallRecord, Store


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "nested" / "dashboard.html"

    def test_empty_store_still_renders(self):
        path = render(self.store, self.out)
        self.assertTrue(path.is_file())
        html = path.read_text(encoding="utf-8")
        self.assertIn("Meter · LLM 调用面板", html)
        self.assertIn("还没有任何调用记录", html)

    def test_renders_models_and_totals(self):
        now = time.time()
        self.store.record(CallRecord(model="gpt-4o", prompt_tokens=1000, completion_tokens=500,
                                     latency_ms=800, ts=now, cost=0.0123))
        self.store.record(CallRecord(model="deepseek-chat", prompt_tokens=2000,
                                     completion_tokens=100, latency_ms=400, ts=now, cost=0.0011))
        html = render(self.store, self.out).read_text(encoding="utf-8")
        self.assertIn("gpt-4o", html)
        self.assertIn("deepseek-chat", html)
        self.assertIn("<svg", html)
        self.assertIn("$0.0134", html)  # 总成本

    def test_failure_row_marked(self):
        self.store.record(CallRecord(model="gpt-4o", ok=False, error="RateLimitError: 429"))
        html = render(self.store, self.out).read_text(encoding="utf-8")
        self.assertIn("RateLimitError: 429", html)
        self.assertIn("失败", html)

    def test_html_is_escaped(self):
        self.store.record(CallRecord(model="<script>alert(1)</script>", tag="<b>x</b>"))
        html = render(self.store, self.out).read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_no_external_resources(self):
        self.store.record(CallRecord(model="gpt-4o"))
        html = render(self.store, self.out).read_text(encoding="utf-8")
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script", html)

    def test_window_label_reflects_days(self):
        html = render(self.store, self.out, days=30).read_text(encoding="utf-8")
        self.assertIn("近 30 天", html)


if __name__ == "__main__":
    unittest.main()
