import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "run_revision",
    Path(__file__).parents[1] / "revision-tasks" / "run_revision.py",
)
run_revision = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_revision)


def test_collapsed_winner_maps_presentations_and_ties_disagreement() -> None:
    def record(presentation: str, winner: str) -> dict[str, str]:
        return {"presentation": presentation, "winner": winner}

    assert (
        run_revision.collapsed_winner([record("A|B", "A"), record("B|A", "B")])
        == "left"
    )
    assert (
        run_revision.collapsed_winner([record("A|B", "B"), record("B|A", "A")])
        == "right"
    )
    assert (
        run_revision.collapsed_winner([record("A|B", "A"), record("B|A", "A")]) == "tie"
    )
    assert (
        run_revision.collapsed_winner([record("A|B", "A"), record("B|A", "tie")])
        == "tie"
    )
