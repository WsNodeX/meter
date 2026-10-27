"""把调用记录渲染成一份单文件 HTML 面板（内联 CSS + 内联 SVG，无外部依赖）。"""

from __future__ import annotations

import html
import time
from pathlib import Path
from typing import Any

from .store import Store

ACCENT = "#2563eb"
ACCENT_SOFT = "#dbeafe"
GREEN = "#059669"
RED = "#dc2626"
INK = "#0f172a"
MUTED = "#64748b"
LINE = "#e2e8f0"

STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 24px 56px;
  background: #f5f7fa; color: #0f172a;
  font: 14px/1.55 -apple-system, "Segoe UI", "PingFang SC",
        "Microsoft YaHei", Roboto, Helvetica, Arial, sans-serif;
}
.wrap { max-width: 1080px; margin: 0 auto; }
header { display: flex; align-items: center; gap: 14px; margin-bottom: 6px; }
.logo {
  width: 40px; height: 40px; border-radius: 11px; flex: 0 0 auto;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 17px; letter-spacing: .5px;
}
h1 { font-size: 21px; margin: 0; letter-spacing: -.3px; }
.sub { color: #64748b; font-size: 12.5px; margin-top: 2px; }
.grid { display: grid; gap: 14px; margin-top: 22px; }
.kpis { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.cards2 { grid-template-columns: 1fr 1fr; }
.card {
  background: #fff; border: 1px solid #e6ebf2; border-radius: 14px;
  padding: 16px 18px; box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
}
.kpi .label { color: #64748b; font-size: 12px; letter-spacing: .2px; }
.kpi .value {
  font-size: 25px; font-weight: 650; margin-top: 6px; letter-spacing: -.6px;
  font-variant-numeric: tabular-nums;
}
.kpi .hint { color: #94a3b8; font-size: 11.5px; margin-top: 3px; }
h2 { font-size: 14px; margin: 0 0 14px; font-weight: 600; letter-spacing: .1px; }
h2 span { color: #94a3b8; font-weight: 400; margin-left: 6px; font-size: 12px; }
.bars { display: flex; flex-direction: column; gap: 11px; }
.bar-row { display: grid; grid-template-columns: 132px 1fr 92px; align-items: center; gap: 10px; }
.bar-name {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.bar-track { height: 9px; background: #eef2f7; border-radius: 99px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, #3b82f6, #6366f1); }
.bar-val { text-align: right; font-variant-numeric: tabular-nums; font-size: 12px; color: #475569; }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th {
  text-align: left; color: #64748b; font-weight: 500; font-size: 11.5px;
  text-transform: uppercase; letter-spacing: .4px;
  padding: 0 10px 9px 0; border-bottom: 1px solid #e9eef5;
}
td { padding: 8px 10px 8px 0; border-bottom: 1px solid #f1f5f9; color: #334155; }
td.mono, th.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px; }
tr:last-child td { border-bottom: none; }
.ok { color: #059669; }
.bad { color: #dc2626; }
.pill {
  display: inline-block; padding: 1px 7px; border-radius: 99px;
  background: #eef2f7; color: #475569; font-size: 11px;
}
footer { margin-top: 26px; color: #94a3b8; font-size: 11.5px; text-align: center; }
.empty { color: #94a3b8; font-size: 12.5px; padding: 8px 0 4px; }
@media (max-width: 860px) {
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cards2 { grid-template-columns: 1fr; }
}
"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _money(value: float) -> str:
    if value >= 1:
        return f"${value:,.2f}"
    if value >= 0.01:
        return f"${value:.4f}"
    return f"${value:.6f}"


def _int(value: int) -> str:
    return f"{int(value):,}"


def _svg_bars(daily: list[dict[str, Any]], width: int = 620, height: int = 190) -> str:
    """近 N 天调用量柱状图（纯 SVG）。"""
    pad_l, pad_r, pad_t, pad_b = 8, 8, 12, 24
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    peak = max((d["calls"] for d in daily), default=0) or 1
    n = max(1, len(daily))
    slot = plot_w / n
    bar_w = min(26.0, slot * 0.58)

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
             f'role="img" aria-label="每日调用量">']
    # 基线
    base_y = pad_t + plot_h
    parts.append(f'<line x1="{pad_l}" y1="{base_y}" x2="{width - pad_r}" y2="{base_y}" '
                 f'stroke="{LINE}" stroke-width="1"/>')
    for i, d in enumerate(daily):
        calls = d["calls"]
        h = (calls / peak) * (plot_h - 6)
        x = pad_l + slot * i + (slot - bar_w) / 2
        y = base_y - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h, 1):.1f}" '
            f'rx="3" fill="{ACCENT}" opacity="{0.35 + 0.65 * (calls / peak):.3f}">'
            f'<title>{_e(d["day"])}: {calls} 次</title></rect>'
        )
        if i % 2 == 0 or i == n - 1:
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{height - 7}" text-anchor="middle" '
                f'font-size="9.5" fill="{MUTED}">{_e(d["day"][5:])}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _svg_line(daily: list[dict[str, Any]], width: int = 620, height: int = 190) -> str:
    """近 N 天成本折线 + 面积图（纯 SVG）。"""
    pad_l, pad_r, pad_t, pad_b = 8, 8, 12, 24
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    peak = max((d["cost"] for d in daily), default=0.0) or 1.0
    n = max(1, len(daily))
    base_y = pad_t + plot_h

    pts = []
    for i, d in enumerate(daily):
        x = pad_l + (plot_w * (i / max(1, n - 1))) if n > 1 else pad_l + plot_w / 2
        y = base_y - (d["cost"] / peak) * (plot_h - 6)
        pts.append((x, y))

    line_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    area_d = (f"M {pts[0][0]:.1f} {base_y:.1f} L "
              + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
              + f" L {pts[-1][0]:.1f} {base_y:.1f} Z")

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
             f'role="img" aria-label="每日成本">']
    parts.append(f'<line x1="{pad_l}" y1="{base_y}" x2="{width - pad_r}" y2="{base_y}" '
                 f'stroke="{LINE}" stroke-width="1"/>')
    parts.append(f'<path d="{area_d}" fill="{ACCENT_SOFT}" opacity=".85"/>')
    parts.append(f'<path d="{line_d}" fill="none" stroke="{ACCENT}" stroke-width="2" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
    for i, (x, y) in enumerate(pts):
        if i % max(2, n // 7) == 0 or i == n - 1:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#fff" '
                         f'stroke="{ACCENT}" stroke-width="1.8">'
                         f'<title>{_e(daily[i]["day"])}: {_money(daily[i]["cost"])}</title></circle>')
            parts.append(f'<text x="{x:.1f}" y="{height - 7}" text-anchor="middle" '
                         f'font-size="9.5" fill="{MUTED}">{_e(daily[i]["day"][5:])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _model_bars(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">还没有任何调用记录。</div>'
    peak = max(r["cost"] for r in rows) or 1.0
    out = ['<div class="bars">']
    for r in rows:
        pct = r["cost"] / peak * 100
        out.append(
            '<div class="bar-row">'
            f'<div class="bar-name" title="{_e(r["model"])}">{_e(r["model"])}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>'
            f'<div class="bar-val">{_money(r["cost"])}</div>'
            "</div>"
        )
    out.append("</div>")
    return "".join(out)


def _recent_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">还没有任何调用记录。</div>'
    head = (
        "<table><thead><tr>"
        '<th>时间</th><th>模型</th><th class="mono">输入</th><th class="mono">输出</th>'
        '<th class="mono">延迟</th><th class="mono">成本</th><th>状态</th>'
        "</tr></thead><tbody>"
    )
    body = []
    for r in rows:
        stamp = time.strftime("%m-%d %H:%M:%S", time.localtime(float(r["ts"])))
        status = ('<span class="ok">成功</span>' if r["ok"]
                  else f'<span class="bad" title="{_e(r["error"])}">失败</span>')
        body.append(
            "<tr>"
            f'<td class="mono">{_e(stamp)}</td>'
            f"<td>{_e(r['model'])}</td>"
            f'<td class="mono">{_int(r["prompt_tokens"])}</td>'
            f'<td class="mono">{_int(r["completion_tokens"])}</td>'
            f'<td class="mono">{float(r["latency_ms"]):,.0f} ms</td>'
            f'<td class="mono">{_money(float(r["cost"]))}</td>'
            f"<td>{status}</td>"
            "</tr>"
        )
    return head + "".join(body) + "</tbody></table>"


def _error_list(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    items = []
    for r in rows:
        stamp = time.strftime("%m-%d %H:%M", time.localtime(float(r["ts"])))
        items.append(
            "<tr>"
            f'<td class="mono">{_e(stamp)}</td>'
            f"<td>{_e(r['model'])}</td>"
            f'<td class="mono bad">{_e((r["error"] or "")[:120])}</td>'
            "</tr>"
        )
    return (
        '<div class="card" style="margin-top:14px">'
        "<h2>最近失败<span>排查用</span></h2>"
        "<table><thead><tr><th>时间</th><th>模型</th><th>错误</th></tr></thead><tbody>"
        + "".join(items)
        + "</tbody></table></div>"
    )


def render(store: Store, out: str | Path = "dashboard.html", days: int = 14) -> Path:
    """渲染面板并写入 ``out``，返回输出路径。"""
    total = store.summary()
    window_start = time.time() - days * 86400
    window = store.summary(window_start)
    models = store.by_model(window_start)
    daily = store.daily(days)
    recent = store.recent(20)
    errors = store.errors(5)

    generated = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    kpis = [
        ("总调用", _int(total["calls"]), f"近 {days} 天 {_int(window['calls'])} 次"),
        ("总成本", _money(total["cost"]),
         f"近 {days} 天 {_money(window['cost'])}"),
        ("平均延迟", f"{total['avg_latency_ms']:,.0f} ms", "全量均值"),
        ("P95 延迟", f"{total['p95_latency_ms']:,.0f} ms", "长尾参考"),
        ("成功率", f"{total['success_rate']}%",
         f"{_int(total['errors'])} 次失败"),
    ]
    kpi_cards = "".join(
        f'<div class="card kpi"><div class="label">{_e(l)}</div>'
        f'<div class="value">{_e(v)}</div><div class="hint">{_e(h)}</div></div>'
        for l, v, h in kpis
    )

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meter · LLM 调用面板</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">M</div>
    <div>
      <h1>Meter · LLM 调用面板</h1>
      <div class="sub">共 {_int(total['calls'])} 次调用 ·
        {_int(total['prompt_tokens'] + total['completion_tokens'])} tokens ·
        生成于 {_e(generated)}</div>
    </div>
  </header>

  <div class="grid kpis">{kpi_cards}</div>

  <div class="grid cards2">
    <div class="card">
      <h2>按模型成本<span>近 {days} 天</span></h2>
      {_model_bars(models)}
    </div>
    <div class="card">
      <h2>每日调用量<span>近 {days} 天</span></h2>
      {_svg_bars(daily)}
    </div>
  </div>

  <div class="grid cards2">
    <div class="card">
      <h2>每日成本<span>近 {days} 天</span></h2>
      {_svg_line(daily)}
    </div>
    <div class="card">
      <h2>模型明细<span>近 {days} 天</span></h2>
      <table><thead><tr><th>模型</th><th class="mono">调用</th>
      <th class="mono">tokens</th><th class="mono">均延迟</th>
      <th class="mono">成功率</th></tr></thead><tbody>
      {"".join(
          f'<tr><td>{_e(m["model"])}</td><td class="mono">{_int(m["calls"])}</td>'
          f'<td class="mono">{_int(m["tokens"])}</td>'
          f'<td class="mono">{m["avg_latency_ms"]:,.0f} ms</td>'
          f'<td class="mono">{m["success_rate"]}%</td></tr>'
          for m in models
      ) or '<tr><td colspan="5" class="empty">暂无数据</td></tr>'}
      </tbody></table>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <h2>最近调用<span>最新 {len(recent)} 条</span></h2>
    {_recent_table(recent)}
  </div>

  {_error_list(errors)}

  <footer>Meter · 零依赖 LLM 观测 · 单文件面板，离线可看</footer>
</div>
</body>
</html>
"""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path
