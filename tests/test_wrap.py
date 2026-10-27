"""wrap 模块测试：上下文管理器、异常路径、usage 兼容。"""

from __future__ import annotations

import unittest

from meter.wrap import Meter


class MeasureTest(unittest.TestCase):
    def setUp(self):
        self.meter = Meter(":memory:")
        self.addCleanup(self.meter.close)

    def test_context_records_success(self):
        with self.meter.measure("gpt-4o", tag="summary") as call:
            call.prompt_tokens = 1000
            call.completion_tokens = 200
        rows = self.meter.store.recent(1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "gpt-4o")
        self.assertEqual(rows[0]["tag"], "summary")
        self.assertEqual(rows[0]["ok"], 1)
        self.assertGreaterEqual(rows[0]["latency_ms"], 0.0)
        self.assertGreater(rows[0]["cost"], 0.0)

    def test_context_records_failure_and_reraises(self):
        with self.assertRaises(ValueError):
            with self.meter.measure("gpt-4o") as call:  # noqa: F841
                raise ValueError("boom")
        row = self.meter.store.recent(1)[0]
        self.assertEqual(row["ok"], 0)
        self.assertIn("boom", row["error"])

    def test_default_tag_applies(self):
        meter = Meter(":memory:", tag="worker-1")
        self.addCleanup(meter.close)
        with meter.measure("gpt-4o"):
            pass
        self.assertEqual(meter.store.recent(1)[0]["tag"], "worker-1")

    def test_explicit_tag_overrides_default(self):
        meter = Meter(":memory:", tag="worker-1")
        self.addCleanup(meter.close)
        with meter.measure("gpt-4o", tag="job-9"):
            pass
        self.assertEqual(meter.store.recent(1)[0]["tag"], "job-9")


class RecordUsageTest(unittest.TestCase):
    def setUp(self):
        self.meter = Meter(":memory:")
        self.addCleanup(self.meter.close)

    def test_openai_style_usage(self):
        self.meter.record_usage("gpt-4o", {"prompt_tokens": 120, "completion_tokens": 40})
        row = self.meter.store.recent(1)[0]
        self.assertEqual(row["prompt_tokens"], 120)
        self.assertEqual(row["completion_tokens"], 40)

    def test_anthropic_style_usage(self):
        self.meter.record_usage("claude-sonnet-4", {"input_tokens": 300, "output_tokens": 90})
        row = self.meter.store.recent(1)[0]
        self.assertEqual(row["prompt_tokens"], 300)
        self.assertEqual(row["completion_tokens"], 90)

    def test_none_usage_is_safe(self):
        self.meter.record_usage("gpt-4o", None)
        row = self.meter.store.recent(1)[0]
        self.assertEqual((row["prompt_tokens"], row["completion_tokens"]), (0, 0))

    def test_record_manual(self):
        rec = self.meter.record("gpt-4o", 10, 5, latency_ms=88.8, tag="manual")
        self.assertIsNotNone(rec.id)
        row = self.meter.store.recent(1)[0]
        self.assertAlmostEqual(row["latency_ms"], 88.8, places=3)


if __name__ == "__main__":
    unittest.main()
