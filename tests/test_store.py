"""store 模块测试（内存数据库）。"""

from __future__ import annotations

import time
import unittest

from meter.store import CallRecord, Store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)

    def test_record_returns_id_and_counts(self):
        cid = self.store.record(CallRecord(model="gpt-4o", prompt_tokens=100, completion_tokens=50))
        self.assertGreater(cid, 0)
        self.assertEqual(self.store.count(), 1)

    def test_cost_is_computed_on_insert(self):
        self.store.record(CallRecord(model="gpt-4o", prompt_tokens=1_000_000, completion_tokens=0))
        rows = self.store.recent(1)
        self.assertAlmostEqual(rows[0]["cost"], 2.5, places=5)

    def test_explicit_cost_wins(self):
        self.store.record(CallRecord(model="gpt-4o", cost=0.42))
        self.assertAlmostEqual(self.store.recent(1)[0]["cost"], 0.42, places=6)

    def test_summary_aggregates(self):
        self.store.record(CallRecord(model="a", prompt_tokens=10, completion_tokens=5,
                                     latency_ms=100, cost=1.0))
        self.store.record(CallRecord(model="a", prompt_tokens=20, completion_tokens=5,
                                     latency_ms=300, cost=2.0))
        self.store.record(CallRecord(model="b", latency_ms=200, cost=3.0, ok=False, error="boom"))
        s = self.store.summary()
        self.assertEqual(s["calls"], 3)
        self.assertEqual(s["errors"], 1)
        self.assertAlmostEqual(s["cost"], 6.0, places=6)
        self.assertAlmostEqual(s["avg_latency_ms"], 200.0, places=3)
        self.assertEqual(s["prompt_tokens"], 30)
        self.assertAlmostEqual(s["success_rate"], 66.7, places=1)

    def test_summary_p95(self):
        for ms in range(1, 101):  # 1..100
            self.store.record(CallRecord(model="x", latency_ms=ms))
        s = self.store.summary()
        self.assertGreater(s["p95_latency_ms"], 90)
        self.assertLessEqual(s["p95_latency_ms"], 100)

    def test_summary_empty(self):
        s = self.store.summary()
        self.assertEqual(s["calls"], 0)
        self.assertEqual(s["success_rate"], 0.0)
        self.assertEqual(s["p95_latency_ms"], 0.0)

    def test_since_filter(self):
        now = time.time()
        self.store.record(CallRecord(model="old", ts=now - 10 * 86400, cost=5.0))
        self.store.record(CallRecord(model="new", ts=now, cost=1.0))
        self.assertAlmostEqual(self.store.summary(now - 86400)["cost"], 1.0, places=6)

    def test_by_model_sorted_by_cost(self):
        self.store.record(CallRecord(model="cheap", cost=0.1))
        self.store.record(CallRecord(model="rich", cost=9.9))
        self.store.record(CallRecord(model="rich", cost=0.1))
        rows = self.store.by_model()
        self.assertEqual(rows[0]["model"], "rich")
        self.assertEqual(rows[0]["calls"], 2)
        self.assertAlmostEqual(rows[0]["cost"], 10.0, places=6)

    def test_daily_has_full_window(self):
        self.store.record(CallRecord(model="x", ts=time.time(), cost=1.0))
        days = self.store.daily(7)
        self.assertEqual(len(days), 7)
        self.assertEqual(sum(d["calls"] for d in days), 1)

    def test_recent_limit_and_order(self):
        for i in range(5):
            self.store.record(CallRecord(model=f"m{i}", ts=time.time() + i))
        rows = self.store.recent(3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["model"], "m4")

    def test_errors_only(self):
        self.store.record(CallRecord(model="ok"))
        self.store.record(CallRecord(model="bad", ok=False, error="boom"))
        errs = self.store.errors()
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]["error"], "boom")

    def test_record_many(self):
        n = self.store.record_many([CallRecord(model="x") for _ in range(10)])
        self.assertEqual(n, 10)
        self.assertEqual(self.store.count(), 10)
        self.assertEqual(self.store.record_many([]), 0)


if __name__ == "__main__":
    unittest.main()
