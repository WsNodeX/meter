"""基于 SQLite 的调用记录存储与聚合查询（标准库 sqlite3）。"""

from __future__ import annotations

import math
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .pricing import estimate_cost

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                REAL    NOT NULL,
    model             TEXT    NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms        REAL    NOT NULL DEFAULT 0,
    ok                INTEGER NOT NULL DEFAULT 1,
    error             TEXT,
    tag               TEXT,
    cost              REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(ts);
CREATE INDEX IF NOT EXISTS idx_calls_model ON calls(model);
"""


@dataclass
class CallRecord:
    """一次 LLM 调用的记录。"""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    ok: bool = True
    error: str | None = None
    tag: str | None = None
    ts: float = field(default_factory=time.time)
    cost: float | None = None
    id: int | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def resolved_cost(self) -> float:
        if self.cost is not None:
            return self.cost
        return estimate_cost(self.model, self.prompt_tokens, self.completion_tokens)


def _percentile(values: list[float], q: float) -> float:
    """线性插值分位数（q 取 0~1）。空列表返回 0。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return float(ordered[int(pos)])
    weight = pos - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


class Store:
    """调用记录的持久化存储。默认落在 ``.meter/meter.db``。"""

    def __init__(self, path: str | Path = ".meter/meter.db") -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------ 写入

    def record(self, call: CallRecord) -> int:
        """写入一条记录，返回自增 id。"""
        cur = self._conn.execute(
            """INSERT INTO calls
               (ts, model, prompt_tokens, completion_tokens, latency_ms, ok, error, tag, cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                call.ts,
                call.model,
                int(call.prompt_tokens or 0),
                int(call.completion_tokens or 0),
                float(call.latency_ms or 0.0),
                1 if call.ok else 0,
                call.error,
                call.tag,
                call.resolved_cost(),
            ),
        )
        self._conn.commit()
        call.id = int(cur.lastrowid)
        return call.id

    def record_many(self, calls: Iterable[CallRecord]) -> int:
        rows = [
            (
                c.ts, c.model, int(c.prompt_tokens or 0), int(c.completion_tokens or 0),
                float(c.latency_ms or 0.0), 1 if c.ok else 0, c.error, c.tag, c.resolved_cost(),
            )
            for c in calls
        ]
        if not rows:
            return 0
        self._conn.executemany(
            """INSERT INTO calls
               (ts, model, prompt_tokens, completion_tokens, latency_ms, ok, error, tag, cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()
        return len(rows)

    # ------------------------------------------------------------------ 查询

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0])

    def summary(self, since: float | None = None) -> dict[str, Any]:
        """总体指标：调用数、成本、token、延迟均值/分位数、成功率。"""
        where, args = ("WHERE ts >= ?", (since,)) if since is not None else ("", ())
        rows = self._conn.execute(
            f"SELECT latency_ms, ok, cost, prompt_tokens, completion_tokens FROM calls {where}",
            args,
        ).fetchall()
        latencies = [float(r["latency_ms"]) for r in rows]
        calls = len(rows)
        ok_count = sum(1 for r in rows if r["ok"])
        return {
            "calls": calls,
            "ok_calls": ok_count,
            "errors": calls - ok_count,
            "cost": round(sum(float(r["cost"]) for r in rows), 6),
            "prompt_tokens": sum(int(r["prompt_tokens"]) for r in rows),
            "completion_tokens": sum(int(r["completion_tokens"]) for r in rows),
            "avg_latency_ms": round(sum(latencies) / calls, 1) if calls else 0.0,
            "p95_latency_ms": round(_percentile(latencies, 0.95), 1),
            "success_rate": round(ok_count / calls * 100, 1) if calls else 0.0,
        }

    def by_model(self, since: float | None = None) -> list[dict[str, Any]]:
        """按模型聚合，按成本降序。"""
        where, args = ("WHERE ts >= ?", (since,)) if since is not None else ("", ())
        rows = self._conn.execute(
            f"""SELECT model,
                       COUNT(*)          AS calls,
                       SUM(cost)         AS cost,
                       SUM(prompt_tokens + completion_tokens) AS tokens,
                       AVG(latency_ms)   AS avg_latency,
                       SUM(ok)           AS ok_calls
                FROM calls {where}
                GROUP BY model
                ORDER BY cost DESC, calls DESC""",
            args,
        ).fetchall()
        out = []
        for r in rows:
            calls = int(r["calls"])
            out.append({
                "model": r["model"],
                "calls": calls,
                "cost": round(float(r["cost"] or 0.0), 6),
                "tokens": int(r["tokens"] or 0),
                "avg_latency_ms": round(float(r["avg_latency"] or 0.0), 1),
                "success_rate": round(int(r["ok_calls"] or 0) / calls * 100, 1) if calls else 0.0,
            })
        return out

    def daily(self, days: int = 14) -> list[dict[str, Any]]:
        """最近 N 天（含无调用的空白天）的每日调用数与成本。"""
        now = time.time()
        start = now - (days - 1) * 86400
        rows = self._conn.execute(
            """SELECT DATE(ts, 'unixepoch', 'localtime') AS day,
                      COUNT(*) AS calls,
                      SUM(cost) AS cost
               FROM calls WHERE ts >= ?
               GROUP BY day ORDER BY day""",
            (start,),
        ).fetchall()
        found = {r["day"]: (int(r["calls"]), float(r["cost"] or 0.0)) for r in rows}
        out = []
        for offset in range(days):
            day_ts = now - (days - 1 - offset) * 86400
            day = time.strftime("%Y-%m-%d", time.localtime(day_ts))
            calls, cost = found.get(day, (0, 0.0))
            out.append({"day": day, "calls": calls, "cost": round(cost, 6)})
        return out

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM calls ORDER BY ts DESC, id DESC LIMIT ?""", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def errors(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM calls WHERE ok = 0 ORDER BY ts DESC, id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
