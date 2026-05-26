"""Static cost lookup tables for LLM models.

All prices are in USD per 1 million tokens. These are approximations —
some providers bill differently for cached or batched tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Cost rates: (prompt_cost_per_1m_tokens, completion_cost_per_1m_tokens)
# ---------------------------------------------------------------------------

COST_TABLE: dict[str, tuple[float, float]] = {
    # OpenAI GPT-4o family
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-11-20": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-2024-05-13": (5.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    # OpenAI GPT-4.1 family
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # OpenAI GPT-4 Turbo / GPT-4
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4-turbo-preview": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-4-32k": (60.00, 120.00),
    # OpenAI GPT-3.5
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-3.5-turbo-0125": (0.50, 1.50),
    # OpenAI o-series
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1-preview": (15.00, 60.00),
    "o3": (10.00, 40.00),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    # Anthropic Claude 4 family
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    # Anthropic Claude 3.7
    "claude-3-7-sonnet-20250219": (3.00, 15.00),
    # Anthropic Claude 3.5 family
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    # Anthropic Claude 3 family
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
}

# Fallback for unknown models
DEFAULT_COST: tuple[float, float] = (1.00, 3.00)


@dataclass
class CostResult:
    """Computed cost breakdown for a single LLM call."""

    prompt_cost_usd: float
    completion_cost_usd: float
    total_cost_usd: float


def compute_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> CostResult:
    """Compute the estimated cost for a model call.

    Args:
        model: The model identifier string.
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.

    Returns:
        A :class:`CostResult` with per-phase and total costs.
    """
    prompt_rate, completion_rate = COST_TABLE.get(model, DEFAULT_COST)

    prompt_cost = (prompt_tokens / 1_000_000) * prompt_rate
    completion_cost = (completion_tokens / 1_000_000) * completion_rate

    return CostResult(
        prompt_cost_usd=round(prompt_cost, 6),
        completion_cost_usd=round(completion_cost, 6),
        total_cost_usd=round(prompt_cost + completion_cost, 6),
    )
