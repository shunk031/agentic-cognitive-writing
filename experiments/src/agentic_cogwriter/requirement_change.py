"""Generate requirement-change items and check two-turn runs against them.

The generator and the checkers use the standard library and stay outside the
run workspace: the runner never stages this module, and ``check`` refuses a run
whose workspace holds a copy of this module or of the items file. The checkers
read only an item, the turn-1 output, and the final output, so they do not
depend on how turn 2 was started.

Requirements. For each prompt of ``PROMPT_IDS``, the output sections are the
``* Name:`` or ``* Name.`` entries of its first requested output constraint.
Turn 1 adds four checkable requirements to the prompt's constraints:

- R1 headings: one Markdown heading per section, with exactly the section's
  text, in order; other headings are allowed;
- R2 bullets: section S_a has exactly n bullet points, n from 3 to 5;
- R3 term: section S_b uses the word w at least twice, where w is the prompt
  text's most frequent word of six or more letters outside ``STOPWORDS`` and
  the section names, ties broken alphabetically;
- R4 ending: the document ends with ``ENDING``.

S_a, S_b, which may coincide, and n come from a random generator seeded with
``SEED`` and the prompt id.

Changes. Each prompt gets one item per class of ``CLASSES`` it can take; a
remove change needs a section other than S_a and S_b. A change replaces
requirements, its choices come from a generator seeded with ``SEED``, the prompt
id, and the class, and its message lists the new requirements without process
words:

- add: R1 gains section L, the first of ``ADDED_SECTIONS`` not already a
  section, after a seeded section S_i, and R5 requires two paragraphs in L;
- bullets: R2's count becomes n + 2;
- term: R3 forbids w in S_b and requires w2, the next such word, twice;
- remove: R1 loses a seeded section S_j other than S_a and S_b, and R5
  forbids a heading with S_j's text, since R1 allows other headings.

A shuffle seeded with ``SEED`` assigns each class to two prompts, repeated until
every prompt can take its class, and marks those items ``assigned``.

Checks. A heading is an ATX heading outside fenced code; its text drops a
closing ``#`` sequence and emphasis that wraps the whole text. A section's
body runs from its first heading with exactly its text to the next heading of
the same or a higher level or naming another of the item's sections, without
``ENDING``. Bullet points are lines starting with ``-``, ``*``, or ``+``,
nested ones included; words match whole and case-insensitively; paragraphs are
blank-line-separated blocks other than a lone heading. A run is checked on its
turn-1 output and its final output:

- incorporated: every changed or added requirement passes after turn 2;
- broken: each unchanged requirement that passed after turn 1 and fails after
  turn 2, with the break rate over the unchanged requirements that passed;
- locality: the share of turn 1's sections, other than the change's target
  (S_a, S_b, or S_j; none for add), present after turn 1 whose
  whitespace-normalized body changed or vanished after turn 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .paths import MANIFESTS_DIR
from .runner.hashing import sha256_json

SEED = 20261028
PROMPT_IDS = (
    "dolomites-1453",
    "dolomites-53",
    "dolomites-673",
    "dolomites-1705",
    "dolomites-247",
    "dolomites-626",
    "dolomites-881",
    "dolomites-296",
)
CLASSES = ("add", "bullets", "term", "remove")
ENDING = "This document follows the stated requirements."
ADDED_SECTIONS = ("Assumptions", "Open Questions", "Glossary", "Next Steps")
_STOPWORD_TEXT = (
    "should would could which their there these those about above below after "
    "before during within without through between including include provide "
    "information document follows stated requirements section sections "
    "paragraph paragraphs sentence sentences following specific describe "
    "details detailed"
)
STOPWORDS = frozenset(_STOPWORD_TEXT.split())
PROCESS_WORDS = ("plan", "goal", "review", "revis", "draft", "translat", "monitor")
_SECTION = re.compile(r"(?:^|\s)\*\s+([^*:.]+?)\s*[:.]\s")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_EMPHASIS = re.compile(r"(\*\*|__|\*|_)(.+)\1")
_BULLET = re.compile(r"^\s*[-*+]\s+\S")


def _words(text: str, excluded: set[str]) -> list[str]:
    counts = Counter(
        word
        for word in re.findall(r"[a-z]{6,}", text.lower())
        if word not in STOPWORDS and word not in excluded
    )
    return sorted(counts, key=lambda word: (-counts[word], word))


def _text(requirement: dict[str, Any]) -> str:
    kind, section = requirement["kind"], requirement.get("section")
    if kind == "headings":
        names = ", ".join(f'"{name}"' for name in requirement["sections"])
        return (
            "Give the document one Markdown heading for each of these sections, "
            f"with exactly this text and in this order: {names}."
        )
    if kind == "bullets":
        return (
            f'The section "{section}" contains exactly {requirement["count"]} '
            "bullet points."
        )
    if kind == "term":
        absent = requirement.get("absent")
        avoid = f'does not use the word "{absent}" at all and ' if absent else ""
        return (
            f'The section "{section}" {avoid}uses the word "{requirement["word"]}" '
            "at least twice."
        )
    if kind == "paragraphs":
        return f'The section "{section}" has at least two paragraphs.'
    if kind == "absent":
        return f'The document has no heading "{section}".'
    return f'The document ends with this sentence: "{ENDING}"'


def _base(prompt_id: str, row: dict[str, Any]) -> dict[str, Any]:
    sections = _SECTION.findall(row["requested_output_constraints"][0])
    rng = random.Random(f"{SEED}:{prompt_id}")
    bullets, term = rng.choice(sections), rng.choice(sections)
    excluded = {word for name in sections for word in name.lower().split()}
    words = _words(row["prompt_text"], excluded)
    return {
        "prompt_id": prompt_id,
        "sections": sections,
        "turn1": [
            {"id": "R1", "kind": "headings", "sections": sections},
            {
                "id": "R2",
                "kind": "bullets",
                "section": bullets,
                "count": rng.choice((3, 4, 5)),
            },
            {"id": "R3", "kind": "term", "section": term, "word": words[0]},
            {"id": "R4", "kind": "ending"},
        ],
        "next_word": words[1],
        "removable": [s for s in sections if s not in (bullets, term)],
    }


def make_items(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one item per prompt and feasible class, in ``PROMPT_IDS`` order."""

    bases = [_base(prompt_id, rows[prompt_id]) for prompt_id in PROMPT_IDS]
    assigned = [kind for kind in CLASSES for _ in range(2)]
    shuffle = random.Random(SEED)
    while True:
        shuffle.shuffle(assigned)
        if all(
            kind != "remove" or base["removable"]
            for kind, base in zip(assigned, bases, strict=True)
        ):
            break
    return [
        _change(base, kind, assigned=kind == pilot)
        for base, pilot in zip(bases, assigned, strict=True)
        for kind in CLASSES
        if kind != "remove" or base["removable"]
    ]


def _change(base: dict[str, Any], kind: str, *, assigned: bool) -> dict[str, Any]:
    prompt_id, sections = base["prompt_id"], base["sections"]
    rng = random.Random(f"{SEED}:{prompt_id}:{kind}")
    turn2 = [dict(requirement) for requirement in base["turn1"]]
    r1, r2, r3 = turn2[0], turn2[1], turn2[2]
    names = list(sections)
    if kind == "add":
        after = rng.choice(sections)
        added = next(
            name
            for name in ADDED_SECTIONS
            if name.lower() not in {s.lower() for s in sections}
        )
        index = sections.index(after) + 1
        r1["sections"] = [*sections[:index], added, *sections[index:]]
        turn2.append({"id": "R5", "kind": "paragraphs", "section": added})
        names.append(added)
        lead = f'Add a section "{added}" directly after the section "{after}".'
        targets: list[str] = []
    elif kind == "bullets":
        r2["count"] += 2
        lead, targets = "", [r2["section"]]
    elif kind == "term":
        r3["absent"], r3["word"] = r3["word"], base["next_word"]
        lead, targets = "", [r3["section"]]
    else:
        removed = rng.choice(base["removable"])
        r1["sections"] = [name for name in sections if name != removed]
        turn2.append({"id": "R5", "kind": "absent", "section": removed})
        lead, targets = f'Remove the section "{removed}".', [removed]
    changed = [r for r in turn2 if r not in base["turn1"]]
    message = "\n".join(
        [
            *([lead] if lead else []),
            "These requirements replace the ones they conflict with; every other "
            "requirement still applies:",
            *(f"- {_text(requirement)}" for requirement in changed),
        ]
    )
    return {
        "id": f"{prompt_id}.{kind}",
        "prompt_id": prompt_id,
        "class": kind,
        "assigned": assigned,
        "sections": names,
        "turn1": base["turn1"],
        "turn2": turn2,
        "changed": [requirement["id"] for requirement in changed],
        "targets": targets,
        "message": message + "\n",
    }


def _derived_row(row: dict[str, Any], turn1: list[dict[str, Any]]) -> dict[str, Any]:
    additional = "Additional requirements:\n" + "\n".join(
        f"- {_text(requirement)}" for requirement in turn1
    )
    derived = {
        **row,
        "requested_output_constraints": [
            *row["requested_output_constraints"],
            additional,
        ],
    }
    derived.pop("hash")
    return {**derived, "hash": sha256_json(derived)}


def generate(out: Path, manifest: Path = MANIFESTS_DIR / "dolomites.jsonl") -> None:
    """Write the derived prompt manifest, the items, and one message per item."""

    rows = {
        row["prompt_id"]: row
        for row in map(json.loads, manifest.read_text(encoding="utf-8").splitlines())
        if row.get("prompt_id") in PROMPT_IDS
    }
    items = make_items(rows)
    turn1 = {item["prompt_id"]: item["turn1"] for item in items}
    (out / "followup").mkdir(parents=True, exist_ok=True)
    (out / "manifest.jsonl").write_text(
        "".join(
            json.dumps(
                _derived_row(rows[prompt_id], turn1[prompt_id]), ensure_ascii=False
            )
            + "\n"
            for prompt_id in PROMPT_IDS
        ),
        encoding="utf-8",
    )
    (out / "items.json").write_text(
        json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for item in items:
        (out / "followup" / f"{item['id']}.txt").write_text(
            item["message"], encoding="utf-8"
        )


def headings(text: str) -> list[tuple[int, int, str]]:
    """Return each heading's line index, level, and text."""

    found, fenced = [], False
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and (match := _HEADING.match(line)):
            name = match.group(2)
            if wrapped := _EMPHASIS.fullmatch(name):
                name = wrapped.group(2)
            found.append((index, len(match.group(1)), name))
    return found


def section_bodies(text: str, names: list[str]) -> dict[str, str]:
    """Map each heading's text, at its first occurrence, to its body."""

    text = text.replace(ENDING, "")
    lines, found = text.splitlines(), headings(text)
    bodies: dict[str, str] = {}
    for position, (index, level, name) in enumerate(found):
        end = next(
            (
                i
                for i, lvl, other in found[position + 1 :]
                if lvl <= level or other in names
            ),
            len(lines),
        )
        bodies.setdefault(name, "\n".join(lines[index + 1 : end]))
    return bodies


def passes(requirement: dict[str, Any], text: str, names: list[str]) -> bool:
    """Return whether ``text`` satisfies one requirement of an item.

    ``names`` are the item's sections, which bound each other's bodies.
    """

    kind = requirement["kind"]
    if kind == "ending":
        return text.rstrip().endswith(ENDING)
    found = [name for _, _, name in headings(text)]
    if kind == "absent":
        return requirement["section"] not in found
    if kind == "headings":
        wanted = requirement["sections"]
        return [name for name in dict.fromkeys(found) if name in wanted] == wanted
    body = section_bodies(text, names).get(requirement["section"])
    if body is None:
        return False
    if kind == "bullets":
        lines = body.splitlines()
        return sum(bool(_BULLET.match(line)) for line in lines) == requirement["count"]
    if kind == "paragraphs":
        blocks = [b for b in re.split(r"\n\s*\n", body) if b.strip()]
        return sum(not _HEADING.match(b.strip()) for b in blocks) >= 2

    def uses(word: str) -> int:
        return len(re.findall(rf"\b{re.escape(word)}\b", body, re.IGNORECASE))

    absent = requirement.get("absent")
    return uses(requirement["word"]) >= 2 and not (absent and uses(absent))


def evaluate(item: dict[str, Any], turn1: str, final: str) -> dict[str, Any]:
    """Return incorporation, breaks, and locality for one run's two outputs."""

    names = item["sections"]
    before = {r["id"]: passes(r, turn1, names) for r in item["turn1"]}
    after = {r["id"]: passes(r, final, names) for r in item["turn2"]}
    kept = [i for i in before if i not in item["changed"] and before[i]]
    broken = [i for i in kept if not after[i]]
    bodies1, bodies2 = section_bodies(turn1, names), section_bodies(final, names)
    untargeted = [
        name
        for name in item["turn1"][0]["sections"]
        if name not in item["targets"] and name in bodies1
    ]
    moved = [
        name
        for name in untargeted
        if name not in bodies2
        or " ".join(bodies1[name].split()) != " ".join(bodies2[name].split())
    ]
    return {
        "item": item["id"],
        "prompt_id": item["prompt_id"],
        "class": item["class"],
        "turn1": before,
        "turn2": after,
        "incorporated": all(after[i] for i in item["changed"]),
        "unchanged_passed_turn1": kept,
        "broken": broken,
        "break_rate": len(broken) / len(kept) if kept else None,
        "untargeted_sections": len(untargeted),
        "changed_untargeted_sections": moved,
        "locality": len(moved) / len(untargeted) if untargeted else None,
    }


def assert_not_staged(workspace: Path, items_path: Path) -> None:
    """Refuse a workspace that holds this module or the items file."""

    digests = {
        hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in (__file__, items_path)
    }
    for path in workspace.rglob("*"):
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() in digests:
            raise RuntimeError(f"{path} copies a generator or checker file")


def check(
    items_path: Path, item_id: str, run_dir: Path, turn1: Path | None = None
) -> dict[str, Any]:
    """Check one run's final output against an item and write ``change-check.json``.

    ``turn1`` defaults to the run's ``turn1/output.normalized.txt`` snapshot.
    """

    assert_not_staged(run_dir / "workspace", items_path)
    item = next(
        item
        for item in json.loads(items_path.read_text(encoding="utf-8"))
        if item["id"] == item_id
    )
    manifest = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
    if manifest["inputs"]["prompt_id"] != item["prompt_id"]:
        raise ValueError(
            f"{run_dir} ran {manifest['inputs']['prompt_id']}, not {item_id}"
        )
    result = evaluate(
        item,
        (turn1 or run_dir / "turn1" / "output.normalized.txt").read_text(
            encoding="utf-8"
        ),
        (run_dir / "output.normalized.txt").read_text(encoding="utf-8"),
    )
    (run_dir / "change-check.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate").add_argument("--out", type=Path, required=True)
    checker = commands.add_parser("check")
    checker.add_argument("--items", type=Path, required=True)
    checker.add_argument("--item", required=True, help="an item id, such as p.term")
    checker.add_argument(
        "--turn1", type=Path, default=None, help="turn-1 output, if not the run's"
    )
    checker.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "generate":
        generate(args.out)
    else:
        print(json.dumps(check(args.items, args.item, args.run_dir, args.turn1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
