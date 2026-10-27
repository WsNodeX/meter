<div align="center">

# Meter

### 零依赖的 LLM 调用观测与成本分析 —— 你的 API 账单不该是一笔糊涂账

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/WsNodeX/meter/actions)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)](https://www.python.org)
[![Dependencies](https://img.shields.io/badge/dependencies-0-lightgrey)](#设计原则)

**接入只要三行代码：记下每次调用的 token、延迟、成本，一条命令生成单文件 HTML 面板。**

<img src="https://cdn.jsdelivr.net/gh/WsNodeX/meter@main/screenshots/dashboard.png" alt="Meter 面板截图" width="860">

</div>

---

## 为什么写它

接了 LLM API 之后，最常见的状态是两眼一抹黑：**这个月烧了多少钱？哪个模型最贵？昨晚那批失败是超时还是限流？** 官方后台的账单是隔天的、聚合的、跟你自己的业务对不上号的。

Meter 把观测搬到你自己的进程里：每次调用一行记录（token / 延迟 / 成功失败），随时生成一张**离线可看的单文件面板**。整个过程不引任何第三方包——解析、存储、画图全用 Python 标准库。

## ✨ 特性

- 🪶 **零依赖**：只用标准库（`sqlite3` / `html` / `argparse`），`pip install` 都省了。
- ⏱️ **侵入极小**：`with meter.measure("gpt-4o"):` 上下文管理器自动计时，异常自动记为失败后原样抛出。
- 💵 **内置价格表**：主流模型（GPT / Claude / DeepSeek / Qwen / GLM / 本地模型）按百万 token 计价，支持前缀匹配版本号，价格表就在一个 dict 里，随时改。
- 🧩 **usage 兼容**：`record_usage()` 直接吃 OpenAI（`prompt_tokens`）和 Anthropic（`input_tokens`）两种字段名。
- 📊 **单文件面板**：输出一个 HTML，内联 CSS + 内联 SVG（柱状 / 折线 / 条形图），无 JS 框架、离线可看、可直接贴截图。
- 🖥️ **CLI**：`demo` / `report` / `stats` 三个子命令，30 秒看到效果。

## 🚀 快速开始

```bash
git clone https://github.com/WsNodeX/meter.git
cd meter

# 不用调模型，先用示例数据看看面板长什么样
python -m meter demo --out dashboard.html --open
```

### 接入你自己的代码

```python
from meter import Meter

meter = Meter()  # 记录落在 .meter/meter.db

with meter.measure("gpt-4o", tag="summary") as call:
    resp = client.chat.completions.create(...)          # 你自己的调用
    call.prompt_tokens = resp.usage.prompt_tokens       # 记 token
    call.completion_tokens = resp.usage.completion_tokens
    # 块内抛异常会记为失败并原样抛出，不用担心吞错

meter.report("dashboard.html")                          # 生成面板
```

一次性记录（拿不到上下文时）：

```python
meter.record_usage("claude-sonnet-4", usage_dict, latency_ms=1234)  # 自动认两种字段名
meter.record("deepseek-chat", prompt_tokens=800, completion_tokens=120,
             latency_ms=650, ok=False, error="RateLimitError: 429")
```

### CLI

```bash
python -m meter stats                       # 终端里看汇总：成本/延迟/成功率
python -m meter report --days 30 --open     # 用已有记录生成面板
```

## 🏗️ 架构

```
 你的业务代码                Meter
┌──────────────┐   with measure()   ┌─────────────┐
│ 调用 LLM API ├───────────────────▶│  wrap.py    │ 自动计时/兜底异常
└──────────────┘                    └──────┬──────┘
                                           │ CallRecord(model, tokens, latency, ok)
                                           ▼
                                    ┌─────────────┐
                                    │  store.py   │ SQLite 存储 + 聚合查询
                                    └──────┬──────┘ (成本 = pricing.py 价格表)
                                           │ summary / by_model / daily
                                           ▼
                                    ┌─────────────┐
                                    │  report.py  │ 单文件 HTML（内联 SVG 图表）
                                    └─────────────┘
```

## 📖 设计原则

- **观测不该比业务重**：接入面只有一个上下文管理器，退出即落库，不碰你的请求/响应结构。
- **面板必须能离线打开**：单文件、内联样式与图表，发给同事或贴工单都不需要起服务。
- **价格表是本地的**：`pricing.py` 就是一张可编辑的 dict；Meter 不联网、不承诺价格权威，需要精确账单请以厂商为准。
- **失败是一等公民**：错误信息、失败次数、最近失败列表都是面板里的固定栏目，不只报喜。

## 🧪 测试

```bash
python -m unittest discover -s tests -t . -v   # 36 个用例
```

覆盖：价格匹配（含前缀命中版本号）、成本计算、聚合与 P95、时间窗过滤、上下文管理器的成功/异常路径、usage 双格式兼容、面板生成与 **HTML 转义（注入安全）**、面板零外部资源。CI 在 Python 3.10 / 3.13 双版本执行。

## 🗺️ 路线图

- [ ] 预算告警：成本/失败率超阈值时回调或退出码
- [ ] `meter export --csv` 导出原始记录
- [ ] 流式响应的 token 累计助手
- [ ] `meter import` 从 JSONL 日志批量导入历史数据

## 🤝 贡献

欢迎 Issue / PR。新功能请保持两个底线：不引入第三方依赖，新逻辑带上测试。

## 📄 许可证

[MIT](LICENSE) © WsNodeX
