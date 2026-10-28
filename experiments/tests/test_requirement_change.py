import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from agentic_cogwriter import requirement_change as rc
from agentic_cogwriter.paths import MANIFESTS_DIR
from agentic_cogwriter.runner.manifest import load_prompt_manifest

# Freezes the generator: any change to the items changes this digest.
ITEMS_SHA256 = "cc0a54cd570e428cee04cd9e174b517f77c67c51690ac1408d29e872957fe99b"
FILLER = (
    "Each campus office records its own figures every term and shares them with "
    "the regional board, which compares the results across sites before the "
    "annual meeting."
)


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
        parts.append(f"## {name}\n\nNotes on {name} only.")
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
        assert all(rc.passes(r, turn2, names, turn1) for r in item["turn2"]), item["id"]
        result = rc.evaluate(item, turn1, turn2)
        assert result["incorporated"] is True
        assert result["broken"] == []
        # A one-section prompt whose section is the target has no locality.
        assert result["locality"] == (0 if result["untargeted_sections"] else None)
        assert result["mean_similarity"] == (
            1 if result["untargeted_sections"] else None
        )
        # The turn-1 document does not already satisfy the change.
        assert not all(rc.passes(r, turn1, names, turn1) for r in item["turn2"]), item[
            "id"
        ]


def test_items_follow_the_frozen_rule(generated: Path) -> None:
    items = _items(generated)
    prompts = {
        row["prompt_id"]: row["prompt_text"].lower()
        for row in map(json.loads, (MANIFESTS_DIR / "dolomites.jsonl").open())
        if row["prompt_id"] in rc.PROMPT_IDS
    }

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
            assert item["message"].startswith(
                f'Remove the section "{removed}" and its content; the task\'s '
                "requirement for that section no longer applies.\n"
            )
        if item["class"] == "term":
            r3 = item["turn2"][2]
            old, new = r3["absent"], r3["word"]
            assert (old, item["changed"]) == (turn1["R3"]["word"], ["R3"])
            assert new not in rc.forms(old) and old not in rc.forms(new)
            # Each word is a base: no shorter prompt token has it as a form.
            vocabulary = set(re.findall(r"[a-z]+", prompts[item["prompt_id"]]))
            for word in (old, new):
                assert not any(word in rc.forms(t) and t != word for t in vocabulary), (
                    word
                )
            # The two words never form a bigram of the prompt text.
            tokens = re.findall(r"[a-z]+", prompts[item["prompt_id"]])
            pairs = set(zip(tokens, tokens[1:], strict=False))
            assert not any(
                (a, b) in pairs or (b, a) in pairs
                for a in rc.forms(old)
                for b in rc.forms(new)
            ), item["id"]
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


def test_word_forms_follow_one_fixed_list() -> None:
    assert rc.forms("project") == {
        "project",
        "projects",
        "projectes",
        "projected",
        "projecting",
    }
    assert {"policies", "policied"} <= rc.forms("policy")
    assert {"changed", "changing"} <= rc.forms("change")
    assert "projection" not in rc.forms("project")


DOCUMENT = (
    "# Report\n\n## Alpha\n\nThe budget and the Budgets.\n\n- a\n- b\n  - c\n\n"
    "* * *\n\n### Detail\n\nMore budgeted text.\n\n```\n## Fenced\n- d\nbudget\n```\n\n"
    "## **Beta** ##\n\nOne.\n\nTwo.\n\n### Gamma\n\nThree.\n\nEpsilon\n-------\n\n"
    "Four.\n\n" + rc.ENDING + "\n"
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
        # A setext heading counts.
        ({"kind": "headings", "sections": ["Gamma", "Epsilon"]}, True),
        # Nested bullets count; a thematic break and fenced code do not.
        ({"kind": "bullets", "section": "Alpha", "count": 3}, True),
        ({"kind": "bullets", "section": "Delta", "count": 0}, False),
        # Forms of a word count, also in a subsection, never inside fenced code.
        ({"kind": "term", "section": "Alpha", "word": "budget"}, True),
        ({"kind": "term", "section": "Detail", "word": "budget"}, False),
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
    ],
)
def test_checkers_test_what_the_requirement_states(
    requirement: dict[str, Any], expected: bool
) -> None:
    assert rc.passes(requirement, DOCUMENT, NAMES) is expected
    assert rc.passes({"kind": "ending"}, DOCUMENT + "Extra.\n", NAMES) is False
    assert "## Fenced" not in rc.section_bodies(DOCUMENT, NAMES)["Alpha"]


def test_a_forbidden_word_fails_in_any_form() -> None:
    term = {"kind": "term", "section": "Alpha", "word": "levy", "absent": "budget"}
    for text in ("levies and levied", "levy and levying"):
        clean = f"## Alpha\n\n{text}.\n"
        assert rc.passes(term, clean, ["Alpha"]) is True
        for form in ("budget", "Budgets", "budgeted", "budgeting"):
            assert rc.passes(term, f"## Alpha\n\n{text}, {form}.\n", ["Alpha"]) is False


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
    swap = f"{r3['word']} and {r3['word']}."

    # One leftover use of the old word, in any form, fails the change.
    for form in (r3["absent"], f"{r3['absent']}s", f"{r3['absent']}ing"):
        kept = final.replace(swap, f"{r3['word']} and {r3['word']}, {form}.")
        assert rc.evaluate(item, turn1, kept)["incorporated"] is False
    # A form of the new word counts.
    inflected = final.replace(swap, f"{r3['word']}s and {r3['word']}ed.")
    assert rc.evaluate(item, turn1, inflected)["incorporated"] is True
    # Rewriting the targeted section is local; rewriting another is not.
    result = rc.evaluate(item, turn1, final)
    assert (result["incorporated"], result["changed_untargeted_sections"]) == (True, [])
    other = next(s for s in item["turn1"][0]["sections"] if s not in item["targets"])
    moved = final.replace(f"Notes on {other} only.", f"Notes on {other} alone.")
    result = rc.evaluate(item, turn1, moved)
    assert result["changed_untargeted_sections"] == [other]
    assert 0.9 < result["untargeted_similarity"][other] < 1


def _remove_case(generated: Path) -> tuple[dict[str, Any], str, str, str]:
    """Return a remove item, a turn-1 output whose removed section has a long
    body, the clean final output, and the removed section's name."""

    item = _item(generated, "remove")
    (removed,) = item["targets"]
    turn1 = witness(item["turn1"]).replace(
        f"Notes on {removed} only.", f"Notes on {removed} only. {FILLER}"
    )
    return item, turn1, witness(item["turn2"]), removed


def test_remove_passes_a_clean_removal(generated: Path) -> None:
    item, turn1, final, _ = _remove_case(generated)

    result = rc.evaluate(item, turn1, final)

    assert (result["incorporated"], result["changed_untargeted_sections"]) == (True, [])


@pytest.mark.parametrize(
    "variant",
    ["preamble", "lowercase", "title", "bold", "setext", "renamed", "merged"],
)
def test_remove_fails_each_false_pass(generated: Path, variant: str) -> None:
    item, turn1, final, removed = _remove_case(generated)
    other = item["turn2"][0]["sections"][0]
    body = f"Notes on {removed} only. {FILLER}"
    final = {
        "preamble": f"{body}\n\n{final}",
        "lowercase": final.replace(rc.ENDING, f"## {removed.lower()}\n\n{rc.ENDING}"),
        "title": final.replace(rc.ENDING, f"## {removed.title()}\n\n{rc.ENDING}"),
        "bold": final.replace(rc.ENDING, f"**{removed}**\n\n{rc.ENDING}"),
        "setext": final.replace(
            rc.ENDING, f"{removed}\n{'=' * len(removed)}\n\n{rc.ENDING}"
        ),
        "renamed": final.replace(rc.ENDING, f"## Other notes\n\n{body}\n\n{rc.ENDING}"),
        "merged": final.replace(
            f"Notes on {other} only.", f"Notes on {other} only.\n\n{body}"
        ),
    }[variant]

    assert rc.evaluate(item, turn1, final)["incorporated"] is False


def test_remove_keeps_a_nested_section_from_moving_its_neighbour(
    generated: Path,
) -> None:
    item, turn1, final, removed = _remove_case(generated)
    nested = turn1.replace(f"## {removed}\n", f"### {removed}\n")

    result = rc.evaluate(item, nested, final)

    assert (result["incorporated"], result["changed_untargeted_sections"]) == (True, [])


def _run_dir(root: Path, prompt_id: str, turn1: str, final: str) -> Path:
    run_dir = root / "DoLoMiTes" / "A4" / "codex" / "run-1"
    (run_dir / "workspace").mkdir(parents=True)
    (run_dir / "turn1").mkdir()
    (run_dir / "turn1" / "output.normalized.txt").write_text(turn1)
    (run_dir / "output.normalized.txt").write_text(final)
    (run_dir / "run-manifest.json").write_text(
        json.dumps({"inputs": {"prompt_id": prompt_id}})
    )
    return run_dir


def test_check_scores_breaks_and_locality_and_writes_outside_the_run(
    generated: Path, tmp_path: Path
) -> None:
    item = _item(generated, "bullets")
    turn1 = witness(item["turn1"])
    # Turn 2 applies the change but drops the ending and rewrites another section.
    other = next(s for s in item["turn1"][0]["sections"] if s not in item["targets"])
    final = witness(item["turn2"]).replace(rc.ENDING, "")
    final = final.replace(f"Notes on {other} only.", "New.")
    run_dir = _run_dir(tmp_path / "runs", item["prompt_id"], "unused", final)
    saved = tmp_path / "saved-turn1.md"
    saved.write_text(turn1)
    out = tmp_path / "checks" / "result.json"

    # The turn-1 output may come from anywhere, such as a saved shared state.
    result = rc.check(generated / "items.json", item["id"], run_dir, out, saved)

    assert result["incorporated"] is True
    assert result["broken"] == ["R4"]
    assert result["break_rate"] == 1 / 3
    assert result["changed_untargeted_sections"] == [other]
    assert result["locality"] == 1 / result["untargeted_sections"]
    assert 0 < result["mean_similarity"] < 1
    assert json.loads(out.read_text()) == result
    assert not (run_dir / "change-check.json").exists()
    other_item = next(
        i["id"] for i in _items(generated) if i["prompt_id"] != item["prompt_id"]
    )
    with pytest.raises(ValueError, match="ran"):
        rc.check(generated / "items.json", other_item, run_dir, out, saved)


@pytest.mark.parametrize("exposure", ["output", "items", "copy", "path", "hash"])
def test_check_refuses_a_run_that_could_see_the_checker(
    generated: Path, tmp_path: Path, exposure: str
) -> None:
    item = _item(generated, "bullets")
    run_dir = _run_dir(tmp_path / "runs", item["prompt_id"], "a", "b")
    items, out = generated / "items.json", tmp_path / "checks" / "result.json"
    rollout = run_dir / "sessions" / "attempt-001" / "rollout-x.jsonl"
    rollout.parent.mkdir(parents=True)
    rollout.write_text("{}\n")
    if exposure == "output":
        out = tmp_path / "runs" / "result.json"
    elif exposure == "items":
        items = tmp_path / "runs" / "items.json"
        shutil.copyfile(generated / "items.json", items)
    elif exposure == "copy":
        shutil.copyfile(generated / "items.json", run_dir / "workspace" / "copy.json")
    elif exposure == "path":
        rollout.write_text(json.dumps({"cmd": f"cat {items.resolve()}"}) + "\n")
    else:
        digest = hashlib.sha256(items.read_bytes()).hexdigest()
        (run_dir / "attempt-001.events.jsonl").write_text(digest + "\n")

    with pytest.raises(RuntimeError):
        rc.check(items, item["id"], run_dir, out)
