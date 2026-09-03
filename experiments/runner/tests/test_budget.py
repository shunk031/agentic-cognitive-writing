import pytest
from experiment_runner.budget import OutputBudget
from experiment_runner.errors import BudgetExceeded


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
