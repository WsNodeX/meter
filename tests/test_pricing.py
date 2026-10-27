"""pricing 模块测试。"""

from __future__ import annotations

import unittest

from meter.pricing import PRICES, estimate_cost, is_known, price_of


class PriceLookupTest(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(price_of("gpt-4o"), PRICES["gpt-4o"])

    def test_case_and_space_insensitive(self):
        self.assertEqual(price_of("  GPT-4o  "), PRICES["gpt-4o"])

    def test_prefix_match_prefers_longest(self):
        # gpt-4o-mini 不能被 gpt-4o 抢走
        self.assertEqual(price_of("gpt-4o-mini-2024-07-18"), PRICES["gpt-4o-mini"])

    def test_unknown_model_is_zero(self):
        self.assertEqual(price_of("some-unknown-model"), (0.0, 0.0))
        self.assertFalse(is_known("some-unknown-model"))

    def test_known_model_flag(self):
        self.assertTrue(is_known("deepseek-chat"))
        # 价格全为 0 的模型（本地模型）视为"未定价"
        self.assertFalse(is_known("local"))


class EstimateCostTest(unittest.TestCase):
    def test_one_million_input_tokens(self):
        in_price, _ = PRICES["gpt-4o"]
        self.assertAlmostEqual(estimate_cost("gpt-4o", 1_000_000, 0), in_price, places=6)

    def test_one_million_output_tokens(self):
        _, out_price = PRICES["gpt-4o"]
        self.assertAlmostEqual(estimate_cost("gpt-4o", 0, 1_000_000), out_price, places=6)

    def test_mixed_usage(self):
        in_price, out_price = PRICES["gpt-4o"]
        expected = in_price * 0.001 + out_price * 0.0005
        self.assertAlmostEqual(estimate_cost("gpt-4o", 1000, 500), expected, places=6)

    def test_zero_and_negative_tokens(self):
        self.assertEqual(estimate_cost("gpt-4o", 0, 0), 0.0)
        self.assertEqual(estimate_cost("gpt-4o", -100, -50), 0.0)

    def test_unknown_model_costs_nothing(self):
        self.assertEqual(estimate_cost("nope", 10_000, 10_000), 0.0)


if __name__ == "__main__":
    unittest.main()
