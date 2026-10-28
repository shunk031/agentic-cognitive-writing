import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter import requirement_change as rc
from agentic_cogwriter.runner.manifest import load_prompt_manifest

# Freezes the generator: any change to the items changes this digest.
ITEMS_SHA256 = "45840d5e0ea2168fbc6eeab6d957a3f314a34911ad734b49ec959164a857b513"


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("generated")
    rc.generate(out)
    return out


def _items(out: Path) -> list[dict[str, Any]]:
    return json.loads((out / "items.json").read_text())


def witness(requirements: list[dict[str, Any]]) -> str:
    """Build a document that satisfies every requirement of one set."""

    headings = next(r for r in requirements if r["kind"] == "headings")
    parts = []
    for name in headings["sections"]:
        parts.append(f"## {name}\n\nText for this part.")
        for requirement in requirements:
            if requirement.get("section") != name:
                continue
            if requirement["kind"] == "bullets":
                count = requirement["count"]
                parts.append("\n".join(f"- Point {k}." for k in range(count)))
            elif requirement["kind"] == "term":
                parts.append(f"{requirement['word']} and {requirement['word']}.")
            elif requirement["kind"] == "paragraphs":
                parts.append("Second part.")
    return "\n\n".join([*parts, rc.ENDING]) + "\n"


def test_generation_is_deterministic_and_frozen(
    generated: Path, tmp_path: Path
) -> None:
    rc.generate(tmp_path)

    for name in ("items.json", "manifest.jsonl"):
        assert (tmp_path / name).read_bytes() == (generated / name).read_bytes()
    digest = hashlib.sha256((generated / "items.json").read_bytes()).hexdigest()
    assert digest == ITEMS_SHA256


def test_every_requirement_set_is_satisfiable(generated: Path) -> None:
    for item in _items(generated):
        turn1, turn2 = witness(item["turn1"]), witness(item["turn2"])

        assert all(rc.passes(r, turn1) for r in item["turn1"]), item["prompt_id"]
        assert all(rc.passes(r, turn2) for r in item["turn2"]), item["prompt_id"]
        result = rc.evaluate(item, turn1, turn2)
        assert result["incorporated"] is True
        assert result["broken"] == []
        # A one-section prompt whose section is the target has no locality.
        assert result["locality"] == (0 if result["untargeted_sections"] else None)
        # The turn-1 document does not already satisfy the change.
        assert not all(rc.passes(r, turn1) for r in item["turn2"])


def test_items_follow_the_frozen_rule(generated: Path) -> None:
    items = _items(generated)

    assert [item["prompt_id"] for item in items] == list(rc.PROMPT_IDS)
    assert Counter(item["class"] for item in items) == dict.fromkeys(rc.CLASSES, 2)
    for item in items:
        sections = item["turn1"][0]["sections"]
        assert sections
        if item["class"] == "remove":
            assert item["targets"][0] not in item["turn2"][0]["sections"]
            assert item["targets"][0] not in (
                item["turn1"][1]["section"],
                item["turn1"][2]["section"],
            )
        # Quoted text comes from the prompt; the rest names no writing process.
        words = re.sub(r'"[^"]*"', "", item["message"]).lower()
        assert not any(word in words for word in rc.PROCESS_WORDS), item["message"]
        message = (generated / "followup" / f"{item['prompt_id']}.txt").read_text()
        assert message == item["message"]


def test_derived_manifest_loads_with_the_turn1_requirements(generated: Path) -> None:
    manifest = load_prompt_manifest(generated / "manifest.jsonl")

    for item in _items(generated):
        constraints = manifest.get(item["prompt_id"]).requested_output_constraints
        assert constraints[-1].startswith("Additional requirements:\n- ")
        assert rc.ENDING in constraints[-1]


DOCUMENT = (
    "# Report\n\n## Alpha\n\nThe budget and the budget.\n\n- a\n- b\n  - c\n\n"
    "### Detail\n\nMore budget text.\n\n## Beta\n\nOne.\n\nTwo.\n\n" + rc.ENDING + "\n"
)


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ({"kind": "headings", "sections": ["Alpha", "Beta"]}, True),
        ({"kind": "headings", "sections": ["Beta", "Alpha"]}, False),
        ({"kind": "headings", "sections": ["Alpha", "Gamma"]}, False),
        # A heading's text must match exactly.
        ({"kind": "headings", "sections": ["alpha", "Beta"]}, False),
        # Nested bullets count, and a subsection belongs to its section.
        ({"kind": "bullets", "section": "Alpha", "count": 3}, True),
        ({"kind": "bullets", "section": "Alpha", "count": 2}, False),
        ({"kind": "bullets", "section": "Gamma", "count": 0}, False),
        ({"kind": "term", "section": "Alpha", "word": "budget"}, True),
        ({"kind": "term", "section": "Beta", "word": "budget"}, False),
        (
            {"kind": "term", "section": "Alpha", "word": "budget", "absent": "text"},
            False,
        ),
        ({"kind": "paragraphs", "section": "Beta"}, True),
        ({"kind": "paragraphs", "section": "Alpha"}, True),
        ({"kind": "ending"}, True),
        ({"kind": "absent", "section": "Gamma"}, True),
        ({"kind": "absent", "section": "Detail"}, False),
    ],
)
def test_checkers_test_what_the_requirement_states(
    requirement: dict[str, Any], expected: bool
) -> None:
    assert rc.passes(requirement, DOCUMENT) is expected
    assert rc.passes({"kind": "ending"}, DOCUMENT + "Extra.\n") is False


def test_check_scores_breaks_and_locality_and_refuses_staged_copies(
    generated: Path, tmp_path: Path
) -> None:
    item = next(i for i in _items(generated) if i["class"] == "bullets")
    turn1 = witness(item["turn1"])
    # Turn 2 applies the change but drops the ending and rewrites another section.
    other = next(s for s in item["turn1"][0]["sections"] if s not in item["targets"])
    turn2 = witness(item["turn2"]).replace(rc.ENDING, "")
    turn2 = turn2.replace(f"## {other}\n\nText for this part.", f"## {other}\n\nNew.")
    run_dir = tmp_path / "run"
    (run_dir / "turn1").mkdir(parents=True)
    (run_dir / "workspace").mkdir()
    (run_dir / "turn1" / "output.normalized.txt").write_text(turn1)
    (run_dir / "output.normalized.txt").write_text(turn2)
    (run_dir / "run-manifest.json").write_text(
        json.dumps({"inputs": {"prompt_id": item["prompt_id"]}})
    )

    result = rc.check(generated / "items.json", run_dir)

    assert result["incorporated"] is True
    assert result["broken"] == ["R4"]
    assert result["break_rate"] == 1 / 3
    assert result["changed_untargeted_sections"] == [other]
    assert result["locality"] == 1 / result["untargeted_sections"]
    assert json.loads((run_dir / "change-check.json").read_text()) == result

    shutil.copyfile(generated / "items.json", run_dir / "workspace" / "copy.json")
    with pytest.raises(RuntimeError, match="copies a generator or checker file"):
        rc.check(generated / "items.json", run_dir)
