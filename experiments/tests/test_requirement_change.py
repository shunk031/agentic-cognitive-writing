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
ITEMS_SHA256 = "feac60748938b48aacfdf6726f8986f7fd7cf915996c2f2caf2b3cde20184e7a"


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
        names = item["sections"]
        turn1, turn2 = witness(item["turn1"]), witness(item["turn2"])

        assert all(rc.passes(r, turn1, names) for r in item["turn1"]), item["id"]
        assert all(rc.passes(r, turn2, names) for r in item["turn2"]), item["id"]
        result = rc.evaluate(item, turn1, turn2)
        assert result["incorporated"] is True
        assert result["broken"] == []
        # A one-section prompt whose section is the target has no locality.
        assert result["locality"] == (0 if result["untargeted_sections"] else None)
        # The turn-1 document does not already satisfy the change.
        assert not all(rc.passes(r, turn1, names) for r in item["turn2"]), item["id"]


def test_items_follow_the_frozen_rule(generated: Path) -> None:
    items = _items(generated)

    by_prompt: dict[str, list[str]] = {}
    for item in items:
        by_prompt.setdefault(item["prompt_id"], []).append(item["class"])
    assert list(by_prompt) == list(rc.PROMPT_IDS)
    # Every prompt takes term; remove needs a section free of R2 and R3.
    single_section = {"dolomites-626", "dolomites-296"}
    for prompt_id, classes in by_prompt.items():
        expected = [
            c for c in rc.CLASSES if c != "remove" or prompt_id not in single_section
        ]
        assert classes == expected, prompt_id
    assigned = [item for item in items if item["assigned"]]
    assert [item["prompt_id"] for item in assigned] == list(rc.PROMPT_IDS)
    assert Counter(item["class"] for item in assigned) == dict.fromkeys(rc.CLASSES, 2)
    for item in items:
        assert item["id"] == f"{item['prompt_id']}.{item['class']}"
        turn1 = {r["id"]: r for r in item["turn1"]}
        if item["class"] == "remove":
            (removed,) = item["targets"]
            assert removed not in item["turn2"][0]["sections"]
            assert removed not in (turn1["R2"]["section"], turn1["R3"]["section"])
            assert item["changed"] == ["R1", "R5"]
        if item["class"] == "term":
            r3 = item["turn2"][2]
            assert (r3["absent"], item["changed"]) == (turn1["R3"]["word"], ["R3"])
            assert r3["word"] != r3["absent"]
            assert item["targets"] == [r3["section"]]
        # Quoted text comes from the prompt; the rest names no writing process.
        words = re.sub(r'"[^"]*"', "", item["message"]).lower()
        assert not any(word in words for word in rc.PROCESS_WORDS), item["message"]
        message = (generated / "followup" / f"{item['id']}.txt").read_text()
        assert message == item["message"]


def test_derived_manifest_loads_with_the_turn1_requirements(generated: Path) -> None:
    manifest = load_prompt_manifest(generated / "manifest.jsonl")

    for item in _items(generated):
        constraints = manifest.get(item["prompt_id"]).requested_output_constraints
        assert constraints[-1].startswith("Additional requirements:\n- ")
        assert rc.ENDING in constraints[-1]


DOCUMENT = (
    "# Report\n\n## Alpha\n\nThe budget and the Budget.\n\n- a\n- b\n  - c\n\n"
    "### Detail\n\nMore budget text, budgets.\n\n```\n## Fenced\n```\n\n"
    "## **Beta** ##\n\nOne.\n\nTwo.\n\n### Gamma\n\nThree.\n\n" + rc.ENDING + "\n"
)
NAMES = ["Alpha", "Beta", "Gamma"]


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ({"kind": "headings", "sections": ["Alpha", "Beta"]}, True),
        ({"kind": "headings", "sections": ["Beta", "Alpha"]}, False),
        ({"kind": "headings", "sections": ["Alpha", "Delta"]}, False),
        # A heading's text must match exactly, apart from wrapping emphasis.
        ({"kind": "headings", "sections": ["alpha", "Beta"]}, False),
        # Nested bullets count, and a subsection belongs to its section.
        ({"kind": "bullets", "section": "Alpha", "count": 3}, True),
        ({"kind": "bullets", "section": "Alpha", "count": 2}, False),
        ({"kind": "bullets", "section": "Delta", "count": 0}, False),
        # Words match whole and case-insensitively, also in a subsection.
        ({"kind": "term", "section": "Alpha", "word": "budget"}, True),
        ({"kind": "term", "section": "Detail", "word": "budget"}, False),
        ({"kind": "term", "section": "Beta", "word": "budget"}, False),
        (
            {"kind": "term", "section": "Alpha", "word": "budget", "absent": "text"},
            False,
        ),
        (
            {"kind": "term", "section": "Alpha", "word": "budget", "absent": "budge"},
            True,
        ),
        # A heading naming another section ends a body at any level.
        ({"kind": "paragraphs", "section": "Beta"}, True),
        ({"kind": "paragraphs", "section": "Gamma"}, False),
        ({"kind": "ending"}, True),
        ({"kind": "absent", "section": "Delta"}, True),
        ({"kind": "absent", "section": "Beta"}, False),
        # Fenced code holds no heading.
        ({"kind": "absent", "section": "Fenced"}, True),
    ],
)
def test_checkers_test_what_the_requirement_states(
    requirement: dict[str, Any], expected: bool
) -> None:
    assert rc.passes(requirement, DOCUMENT, NAMES) is expected
    assert rc.passes({"kind": "ending"}, DOCUMENT + "Extra.\n", NAMES) is False


def _item(generated: Path, kind: str, *, multi: bool = True) -> dict[str, Any]:
    return next(
        item
        for item in _items(generated)
        if item["class"] == kind and (len(item["turn1"][0]["sections"]) > 2) == multi
    )


def test_term_swap_scores_the_swap_and_its_section_alone(generated: Path) -> None:
    item = _item(generated, "term")
    r3 = item["turn2"][2]
    turn1 = witness(item["turn1"])
    final = witness(item["turn2"])

    # Keeping one use of the old word fails the change.
    kept = final.replace(
        f"{r3['word']} and {r3['word']}.",
        f"{r3['word']} and {r3['word']}, {r3['absent']}.",
    )
    assert rc.evaluate(item, turn1, kept)["incorporated"] is False
    # Rewriting the targeted section is local; rewriting another is not.
    result = rc.evaluate(item, turn1, final)
    assert (result["incorporated"], result["changed_untargeted_sections"]) == (True, [])
    other = next(s for s in item["turn1"][0]["sections"] if s not in item["targets"])
    moved = final.replace(f"## {other}\n\nText for this part.", f"## {other}\n\nNew.")
    assert rc.evaluate(item, turn1, moved)["changed_untargeted_sections"] == [other]


def test_remove_scores_the_heading_and_keeps_neighbours_local(generated: Path) -> None:
    item = _item(generated, "remove")
    (removed,) = item["targets"]
    turn1 = witness(item["turn1"])
    final = witness(item["turn2"])

    assert rc.evaluate(item, turn1, final)["incorporated"] is True
    # Keeping the heading, even with emphasis or demoted, fails the change.
    for heading in (f"## **{removed}**", f"#### {removed}"):
        kept = final.replace(rc.ENDING, f"{heading}\n\nOld.\n\n{rc.ENDING}")
        assert rc.evaluate(item, turn1, kept)["incorporated"] is False
    # The removed section was nested under a neighbour in turn 1; removing it
    # leaves the neighbour unchanged.
    nested = turn1.replace(f"## {removed}\n", f"### {removed}\n")
    result = rc.evaluate(item, nested, final)
    assert (result["incorporated"], result["changed_untargeted_sections"]) == (True, [])


def test_check_scores_breaks_and_locality_and_refuses_staged_copies(
    generated: Path, tmp_path: Path
) -> None:
    item = _item(generated, "bullets")
    turn1 = witness(item["turn1"])
    # Turn 2 applies the change but drops the ending and rewrites another section.
    other = next(s for s in item["turn1"][0]["sections"] if s not in item["targets"])
    final = witness(item["turn2"]).replace(rc.ENDING, "")
    final = final.replace(f"## {other}\n\nText for this part.", f"## {other}\n\nNew.")
    run_dir = tmp_path / "run"
    (run_dir / "workspace").mkdir(parents=True)
    saved = tmp_path / "saved-turn1.md"
    saved.write_text(turn1)
    (run_dir / "output.normalized.txt").write_text(final)
    (run_dir / "run-manifest.json").write_text(
        json.dumps({"inputs": {"prompt_id": item["prompt_id"]}})
    )

    # The turn-1 output may come from anywhere, such as a saved shared state.
    result = rc.check(generated / "items.json", item["id"], run_dir, saved)

    assert result["incorporated"] is True
    assert result["broken"] == ["R4"]
    assert result["break_rate"] == 1 / 3
    assert result["changed_untargeted_sections"] == [other]
    assert result["locality"] == 1 / result["untargeted_sections"]
    assert json.loads((run_dir / "change-check.json").read_text()) == result
    with pytest.raises(ValueError, match="ran"):
        other_item = next(
            i["id"] for i in _items(generated) if i["prompt_id"] != item["prompt_id"]
        )
        rc.check(generated / "items.json", other_item, run_dir, saved)

    shutil.copyfile(generated / "items.json", run_dir / "workspace" / "copy.json")
    with pytest.raises(RuntimeError, match="copies a generator or checker file"):
        rc.check(generated / "items.json", item["id"], run_dir, saved)
