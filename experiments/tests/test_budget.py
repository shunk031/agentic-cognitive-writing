import pytest

from agentic_cogwriter.runner.budget import OutputBudget, estimate_output_tokens
from agentic_cogwriter.runner.errors import BudgetExceeded


def test_output_budget_tracks_total_across_sequential_stages():
    budget = OutputBudget(5)

    budget.consume(3, stage="pre_write")
    budget.consume(2, stage="write")

    assert budget.used == 5
    assert budget.remaining == 0


def test_output_budget_rejects_overflow_without_partial_consumption():
    budget = OutputBudget(5)
    budget.consume(4, stage="draft")

    with pytest.raises(BudgetExceeded, match="polish"):
        budget.consume(2, stage="polish")

    assert budget.used == 4
    assert budget.remaining == 1


def test_estimate_output_tokens_counts_cjk_codepoints_and_preserves_english() -> None:
    assert estimate_output_tokens("one two\nthree") == 3
    assert estimate_output_tokens("中文 mixed-script") == 3
    assert estimate_output_tokens("pre中post") == 3
