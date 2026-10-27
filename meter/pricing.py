"""模型价格表与成本估算。

单位统一为「美元 / 每百万 token」。价格是本地可编辑的静态表，不是权威报价，
随时可能变动 —— 需要精确账单时请以厂商官方计价为准。
"""

from __future__ import annotations

MILLION = 1_000_000.0

#: model -> (输入单价, 输出单价)，单位：美元 / 百万 token
PRICES: dict[str, tuple[float, float]] = {
    # OpenAI 风格
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "o3-mini": (1.10, 4.40),
    # Anthropic 风格
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-4": (0.80, 4.00),
    "claude-opus-4": (15.00, 75.00),
    # 国内常见模型
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "qwen-plus": (0.40, 1.20),
    "qwen-max": (2.40, 9.60),
    "glm-4-plus": (0.70, 0.70),
    "ernie-4.0": (1.40, 4.20),
    # 本地模型
    "local": (0.0, 0.0),
}


def price_of(model: str) -> tuple[float, float]:
    """返回模型的 (输入单价, 输出单价)；未知模型返回 (0, 0)。

    大小写与首尾空格不敏感；支持前缀匹配（``gpt-4o-2024-08-06`` 命中 ``gpt-4o``）。
    """
    key = (model or "").strip().lower()
    if key in PRICES:
        return PRICES[key]
    # 前缀匹配：取最长的匹配键，避免 gpt-4o-mini 被 gpt-4o 抢先命中
    candidates = [k for k in PRICES if key.startswith(k)]
    if candidates:
        return PRICES[max(candidates, key=len)]
    return (0.0, 0.0)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """按 token 用量估算单次调用成本（美元）。"""
    in_price, out_price = price_of(model)
    tokens_in = max(0, int(prompt_tokens or 0))
    tokens_out = max(0, int(completion_tokens or 0))
    cost = (tokens_in / MILLION) * in_price + (tokens_out / MILLION) * out_price
    return round(cost, 8)


def is_known(model: str) -> bool:
    """该模型是否在价格表内（不在表内的成本会被记为 0）。"""
    return price_of(model) != (0.0, 0.0)
