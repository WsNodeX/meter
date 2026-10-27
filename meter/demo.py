"""示例数据生成器：不用真的调用模型，也能看到面板长什么样。"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from .store import CallRecord

if TYPE_CHECKING:  # pragma: no cover
    from .wrap import Meter

# (模型, 权重, 平均输入 token, 平均输出 token)
PROFILES = [
    ("gpt-4o", 18, 1800, 520),
    ("gpt-4o-mini", 34, 950, 260),
    ("claude-sonnet-4", 14, 2200, 700),
    ("deepseek-chat", 22, 1400, 420),
    ("qwen-plus", 9, 800, 300),
    ("local", 3, 600, 200),
]

TAGS = ["chat", "summary", "extract", "classify", "rag-answer"]
ERRORS = [
    "RateLimitError: 429 rate limit exceeded",
    "APITimeoutError: request timed out after 60s",
    "BadRequestError: context length exceeded",
]


def seed(meter: "Meter", days: int = 14, per_day: int = 60, seed_value: int = 7) -> int:
    """写入 ``days`` 天的示例调用记录，返回写入条数。"""
    rng = random.Random(seed_value)
    now = time.time()
    records: list[CallRecord] = []

    for day_offset in range(days):
        day_start = now - (days - 1 - day_offset) * 86400
        # 工作日更忙，周末少一些
        weekday = time.localtime(day_start).tm_wday
        factor = 0.55 if weekday >= 5 else 1.0
        count = max(3, int(per_day * factor * rng.uniform(0.7, 1.3)))
        for _ in range(count):
            model, weight, base_in, base_out = rng.choices(
                PROFILES, weights=[p[1] for p in PROFILES], k=1
            )[0]
            prompt = max(80, int(rng.gauss(base_in, base_in * 0.35)))
            completion = max(20, int(rng.gauss(base_out, base_out * 0.4)))
            # 延迟：偏态分布，偶发长尾
            latency = rng.gauss(1200, 350)
            if rng.random() < 0.06:
                latency += rng.uniform(1500, 4000)
            ok = rng.random() > 0.035
            records.append(CallRecord(
                model=model,
                prompt_tokens=prompt,
                completion_tokens=0 if not ok else completion,
                latency_ms=max(80.0, round(latency, 1)),
                ok=ok,
                error=None if ok else rng.choice(ERRORS),
                tag=rng.choice(TAGS),
                ts=day_start + rng.uniform(0, 86400 * 0.92),
            ))

    records.sort(key=lambda r: r.ts)
    return meter.store.record_many(records)


if __name__ == "__main__":  # pragma: no cover
    from .wrap import Meter

    m = Meter(".meter/demo.db")
    print("写入", seed(m), "条")
    print(m.report("dashboard.html"))
