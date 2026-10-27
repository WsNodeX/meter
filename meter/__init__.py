"""Meter —— 零依赖的 LLM 调用观测与成本分析工具。

快速上手::

    from meter import Meter

    meter = Meter()                       # 默认写入 .meter/meter.db
    with meter.measure("gpt-4o", tag="summary") as call:
        call.prompt_tokens = 1200
        call.completion_tokens = 350
        # 真正调用模型...

    meter.report("dashboard.html")        # 生成单文件 HTML 面板
"""

from __future__ import annotations

from .pricing import PRICES, estimate_cost, price_of
from .store import CallRecord, Store
from .wrap import Meter, MeteredCall

__all__ = [
    "PRICES",
    "CallRecord",
    "Meter",
    "MeteredCall",
    "Store",
    "estimate_cost",
    "price_of",
]

__version__ = "1.0.0"
