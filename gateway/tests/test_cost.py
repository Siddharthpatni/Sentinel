"""Unit tests for the cost computation engine."""

from __future__ import annotations

import pytest

from app.tracing.cost import COST_TABLE, DEFAULT_COST, CostResult, compute_cost


class TestComputeCost:
    """Tests for the compute_cost function."""

    def test_known_model(self) -> None:
        """GPT-4o-mini should use its known rates."""
        result = compute_cost("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=1_000_000)
        assert isinstance(result, CostResult)
        assert result.prompt_cost_usd == 0.15
        assert result.completion_cost_usd == 0.60
        assert result.total_cost_usd == 0.75

    def test_unknown_model_uses_default(self) -> None:
        """Unknown model should fall back to DEFAULT_COST."""
        result = compute_cost("unknown-model-xyz", prompt_tokens=1_000_000, completion_tokens=1_000_000)
        prompt_rate, completion_rate = DEFAULT_COST
        assert result.prompt_cost_usd == prompt_rate
        assert result.completion_cost_usd == completion_rate

    def test_zero_tokens(self) -> None:
        """Zero tokens should produce zero cost."""
        result = compute_cost("gpt-4o", prompt_tokens=0, completion_tokens=0)
        assert result.total_cost_usd == 0.0

    def test_small_token_count(self) -> None:
        """Small token counts should compute correctly with precision."""
        result = compute_cost("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
        # 100 / 1M * 0.15 = 0.000015
        # 50 / 1M * 0.60 = 0.00003
        assert result.total_cost_usd == pytest.approx(0.000045, abs=1e-6)

    def test_anthropic_model(self) -> None:
        """Claude 3.5 Sonnet should use Anthropic's rates."""
        result = compute_cost(
            "claude-3-5-sonnet-20241022",
            prompt_tokens=500_000,
            completion_tokens=200_000,
        )
        assert result.prompt_cost_usd == 1.5  # 0.5M * 3.0/M
        assert result.completion_cost_usd == 3.0  # 0.2M * 15.0/M
        assert result.total_cost_usd == 4.5

    def test_all_models_have_two_rates(self) -> None:
        """Every entry in COST_TABLE should be a 2-tuple of floats."""
        for model, rates in COST_TABLE.items():
            assert len(rates) == 2, f"{model} has {len(rates)} rates"
            assert all(isinstance(r, (int, float)) for r in rates), f"{model} has non-numeric rates"
