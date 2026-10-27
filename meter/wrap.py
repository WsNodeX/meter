"""用上下文管理器或显式调用记录一次 LLM 请求。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .store import CallRecord, Store


class MeteredCall:
    """一次被观测的调用。退出上下文时自动写入记录。

    用法::

        with meter.measure("gpt-4o", tag="summary") as call:
            resp = client.chat(...)
            call.prompt_tokens = resp.usage.prompt_tokens
            call.completion_tokens = resp.usage.completion_tokens

    在 ``with`` 块内抛出异常时，记录会标记为失败并保存异常信息后原样抛出。
    """

    def __init__(self, meter: "Meter", model: str, tag: str | None) -> None:
        self._meter = meter
        self.model = model
        self.tag = tag
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.ok = True
        self.error: str | None = None
        self._start = 0.0
        self.record: CallRecord | None = None

    def __enter__(self) -> "MeteredCall":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        latency_ms = (time.perf_counter() - self._start) * 1000.0
        if exc is not None:
            self.ok = False
            self.error = f"{exc_type.__name__}: {exc}" if exc_type else str(exc)
        self.record = CallRecord(
            model=self.model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            latency_ms=round(latency_ms, 3),
            ok=self.ok,
            error=self.error,
            tag=self.tag,
        )
        self._meter._store.record(self.record)
        return False  # 不吞异常


class Meter:
    """对外门面：一个 store + 便捷的记录方法。"""

    def __init__(self, path: str | Path = ".meter/meter.db", tag: str | None = None) -> None:
        self._store = Store(path)
        self.default_tag = tag

    # ------------------------------------------------------------------ 记录

    def measure(self, model: str, tag: str | None = None) -> MeteredCall:
        """上下文管理器：自动计时并在退出时写入。"""
        return MeteredCall(self, model, tag if tag is not None else self.default_tag)

    def record(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0.0,
        ok: bool = True,
        error: str | None = None,
        tag: str | None = None,
    ) -> CallRecord:
        """直接写入一条记录（无上下文场景，如事后导入日志）。"""
        call = CallRecord(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            ok=ok,
            error=error,
            tag=tag if tag is not None else self.default_tag,
        )
        self._store.record(call)
        return call

    def record_usage(
        self,
        model: str,
        usage: dict[str, Any] | None,
        latency_ms: float = 0.0,
        ok: bool = True,
        error: str | None = None,
        tag: str | None = None,
    ) -> CallRecord:
        """从厂商返回的 usage 字典里自动取 token 数（兼容 OpenAI / Anthropic 两种字段名）。"""
        usage = usage or {}
        prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
        return self.record(
            model=model,
            prompt_tokens=int(prompt or 0),
            completion_tokens=int(completion or 0),
            latency_ms=latency_ms,
            ok=ok,
            error=error,
            tag=tag,
        )

    # ------------------------------------------------------------------ 查询

    @property
    def store(self) -> Store:
        return self._store

    def summary(self, days: int | None = None) -> dict[str, Any]:
        since = time.time() - days * 86400 if days else None
        return self._store.summary(since)

    def report(self, out: str | Path = "dashboard.html", days: int = 14) -> Path:
        """生成单文件 HTML 面板，返回输出路径。"""
        from .report import render

        return render(self._store, out, days=days)

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> "Meter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
