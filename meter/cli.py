"""命令行入口：``python -m meter <命令>``。"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from .wrap import Meter


def _cmd_report(args: argparse.Namespace) -> int:
    db = Path(args.db)
    if not db.exists():
        print(f"找不到数据库 {db}，先跑一次 python -m meter demo 看看效果？", file=sys.stderr)
        return 1
    meter = Meter(db)
    try:
        out = meter.report(args.out, days=args.days)
    finally:
        meter.close()
    print(f"面板已生成: {out}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    from .demo import seed

    db = Path(args.db)
    if db.exists():
        db.unlink()
    meter = Meter(db)
    try:
        inserted = seed(meter, days=args.days)
        out = meter.report(args.out, days=min(args.days, 14))
    finally:
        meter.close()
    print(f"已写入 {inserted} 条示例记录 -> {db}")
    print(f"面板已生成: {out}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    meter = Meter(args.db)
    try:
        s = meter.summary(days=args.days)
    finally:
        meter.close()
    print(f"调用数    {s['calls']}")
    print(f"总成本    ${s['cost']:.4f}")
    print(f"平均延迟  {s['avg_latency_ms']:.0f} ms")
    print(f"P95 延迟  {s['p95_latency_ms']:.0f} ms")
    print(f"成功率    {s['success_rate']}%")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="meter", description="零依赖 LLM 调用观测与成本分析")
    p.add_argument("--version", action="version", version="meter 1.0.0")
    sub = p.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("report", help="用已有记录生成 HTML 面板")
    rep.add_argument("--db", default=".meter/meter.db")
    rep.add_argument("--out", default="dashboard.html")
    rep.add_argument("--days", type=int, default=14)
    rep.add_argument("--open", action="store_true", help="生成后自动打开")
    rep.set_defaults(func=_cmd_report)

    dem = sub.add_parser("demo", help="生成示例数据并出面板（不用真调模型）")
    dem.add_argument("--db", default=".meter/demo.db")
    dem.add_argument("--out", default="dashboard.html")
    dem.add_argument("--days", type=int, default=14)
    dem.add_argument("--open", action="store_true")
    dem.set_defaults(func=_cmd_demo)

    st = sub.add_parser("stats", help="终端里打印汇总指标")
    st.add_argument("--db", default=".meter/meter.db")
    st.add_argument("--days", type=int, default=None)
    st.set_defaults(func=_cmd_stats)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
