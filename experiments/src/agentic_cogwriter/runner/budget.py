"""Shared output budget accounting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .errors import BudgetExceeded

_CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002FA1F]")


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
                f"Stage {stage} needs {amount} output units but only "
                f"{self.remaining} remain"
            )
        self.used += amount
        self.stages.append((stage, amount))


def estimate_output_tokens(text: str) -> int:
    """Count CJK codepoints and whitespace-separated non-CJK runs."""

    return len(_CJK_RE.findall(text)) + sum(
        len(part.split()) for part in _CJK_RE.split(text)
    )
