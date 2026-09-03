"""Shared output budget accounting."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import BudgetExceeded


@dataclass
class OutputBudget:
    """Count output units across all turns in one condition and prompt run."""

    limit: int
    used: int = 0
    stages: list[tuple[str, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("Output budget limit must be positive")

    @property
    def remaining(self) -> int:
        """Return the unconsumed budget."""

        return self.limit - self.used

    def consume(self, amount: int, *, stage: str) -> None:
        """Consume units atomically, rejecting a stage that would overflow."""

        if amount < 0:
            raise ValueError("Output consumption cannot be negative")
        if amount > self.remaining:
            raise BudgetExceeded(
                f"Stage {stage} needs {amount} output units but only {self.remaining} remain"
            )
        self.used += amount
        self.stages.append((stage, amount))


def estimate_output_tokens(text: str) -> int:
    """Use a deterministic conservative fallback when a pinned tokenizer is unavailable."""

    if not text.strip():
        return 0
    return len(text.split())
