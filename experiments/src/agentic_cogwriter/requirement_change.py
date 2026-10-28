"""Generate requirement-change items and check two-turn runs against them.

The generator and the checkers use the standard library and stay outside the
run workspace and the run output root. ``check`` refuses a run whose workspace
holds a copy of this module or of the items file, or whose harness records name
the module path, the items path, or the items file's hash. The checkers read
only an item, the turn-1 output, and the final output, so they do not depend
on how turn 2 was started.

Requirements. For each prompt of ``PROMPT_IDS``, the output sections are the
``* Name:`` or ``* Name.`` entries of its first requested output constraint.
Turn 1 adds four checkable requirements to the prompt's constraints:

- R1 headings: one Markdown heading per section, with exactly the section's
  text, in order; other headings are allowed;
- R2 bullets: section S_a has exactly n bullet points, n from 3 to 5;
- R3 term: section S_b uses the word w, counting its forms, at least twice,
  where w is the prompt text's most frequent base of six or more letters
  outside ``STOPWORDS`` and the section names, ties broken alphabetically; a
  token's base is the shortest token of the text of which it is a form;
- R4 ending: the document ends with ``ENDING``.

S_a, S_b, which may coincide, and n come from a random generator seeded with
``SEED`` and the prompt id. A word's forms are the word and the word plus
``s``, ``es``, ``ed``, or ``ing``; a word ending in ``y`` also takes ``ies``
and ``ied`` for the ``y``, and a word ending in ``e`` also takes ``d`` and
drops the ``e`` before ``ing``.

Changes. Each prompt gets one item per class of ``CLASSES`` it can take; a
remove change needs a section other than S_a and S_b. A change replaces
requirements, its choices come from a generator seeded with ``SEED``, the prompt
id, and the class, and its message lists the new requirements without process
words:

- add: R1 gains section L, the first of ``ADDED_SECTIONS`` not already a
  section, after a seeded section S_i, and R5 requires two paragraphs in L;
- bullets: R2's count becomes n + 2;
- term: R3 forbids every form of w in S_b and requires a form of w2 twice,
  where w2 is the next such base whose tokens never stand next to tokens of w,
  in either order, in the prompt text;
- remove: R1 loses a seeded section S_j other than S_a and S_b, the message
  retires the task's requirement for S_j, and R5 forbids S_j's heading and
  content.

A shuffle seeded with ``SEED`` assigns each class to two prompts, repeated until
every prompt can take its class, and marks those items ``assigned``.

Checks. A heading is an ATX heading, or a setext heading whose underline
follows a non-blank line, outside fenced code; its text drops a closing ``#``
sequence and emphasis that wraps the whole text. A section's body runs from its
first heading with exactly its text to the next heading of the same or a
higher level or naming another of the item's sections, without fenced code or
``ENDING``. Bullet points are lines starting with ``-``, ``*``, or ``+``,
nested ones included, and a thematic break is not one; words match whole and
case-insensitively; paragraphs are blank-line-separated blocks other than a
lone heading. R5 of a remove change passes when no heading or line that is
wholly bold matches S_j case-insensitively, and at most ``SURVIVAL`` of the
distinct four-word sequences of S_j's turn-1 body occur anywhere in the final
output. A run is checked on its turn-1 output and its final output:

- incorporated: every changed or added requirement passes after turn 2;
- broken: each unchanged requirement that passed after turn 1 and fails after
  turn 2, with the break rate over the unchanged requirements that passed;
- locality: over turn 1's sections, other than the change's target (S_a, S_b,
  or S_j; none for add), present after turn 1, the share whose
  whitespace-normalized body changed or vanished after turn 2, and the mean
  ``difflib.SequenceMatcher`` ratio of each body before and after, zero for a
  vanished one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from difflib import SequenceMatcher
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
SURVIVAL = 0.2
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
_SETEXT = re.compile(r"^ {0,3}(=+|-+)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_EMPHASIS = re.compile(r"(\*\*|__|\*|_)(.+)\1")
_BOLD_LINE = re.compile(r"^\s*(\*\*|__)(.+?)\1\s*:?\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+\S")
_BREAK = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")


def forms(word: str) -> set[str]:
    """Return the inflected forms that count as ``word``."""

    found = {word, f"{word}s", f"{word}es", f"{word}ed", f"{word}ing"}
    if word.endswith("y"):
        found |= {f"{word[:-1]}ies", f"{word[:-1]}ied"}
    if word.endswith("e"):
        found |= {f"{word}d", f"{word[:-1]}ing"}
    return found


def _bases(text: str) -> list[str]:
    """Return each token of ``text`` as its base: the shortest token of the text
    of which it is a form, ties broken alphabetically."""

    tokens = re.findall(r"[a-z]+", text.lower())
    owners: dict[str, list[str]] = {}
    for token in set(tokens):
        for form in forms(token):
            owners.setdefault(form, []).append(token)
    return [min(owners[token], key=lambda t: (len(t), t)) for token in tokens]


def _words(text: str, excluded: set[str]) -> list[str]:
    counts = Counter(
        base
        for base in _bases(text)
        if len(base) >= 6 and base not in STOPWORDS and base not in excluded
    )
    return sorted(counts, key=lambda word: (-counts[word], word))


def _replacement(word: str, candidates: list[str], text: str) -> str:
    """Return the first candidate that never stands next to ``word`` in
    ``text``, comparing bases, in either order."""

    bases = _bases(text)
    pairs = set(zip(bases, bases[1:], strict=False))
    for candidate in candidates:
        if (word, candidate) not in pairs and (candidate, word) not in pairs:
            return candidate
    raise ValueError(f"No replacement word for {word!r}")


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
        avoid = f'does not use the word "{absent}" in any form, and ' if absent else ""
        return (
            f'The section "{section}" {avoid}uses the word "{requirement["word"]}" '
            "at least twice; its forms ending in -s, -es, -ed, or -ing count."
        )
    if kind == "paragraphs":
        return f'The section "{section}" has at least two paragraphs.'
    if kind == "absent":
        return (
            f'The document has no heading or bold line "{section}", in any '
            "capitalization, and does not keep that section's content."
        )
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
        "next_word": _replacement(words[0], words[1:], row["prompt_text"]),
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
        lead = (
            f'Remove the section "{removed}" and its content; the task\'s '
            "requirement for that section no longer applies."
        )
        targets = [removed]
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


def _unfenced(lines: list[str]) -> list[bool]:
    """Return whether each line lies outside fenced code."""

    outside, fenced = [], False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
            outside.append(False)
        else:
            outside.append(not fenced)
    return outside


def headings(text: str) -> list[tuple[int, int, str]]:
    """Return each heading's last line index, level, and text."""

    lines = text.splitlines()
    outside = _unfenced(lines)
    found = []
    for index, line in enumerate(lines):
        if not outside[index]:
            continue
        if match := _HEADING.match(line):
            level, name = len(match.group(1)), match.group(2)
        elif (
            (underline := _SETEXT.match(line))
            and index
            and outside[index - 1]
            and lines[index - 1].strip()
            and not _HEADING.match(lines[index - 1])
            and not _BULLET.match(lines[index - 1])
            and not _BREAK.match(lines[index - 1])
        ):
            level, name = (
                (1 if underline.group(1)[0] == "=" else 2),
                lines[index - 1].strip(),
            )
        else:
            continue
        if wrapped := _EMPHASIS.fullmatch(name):
            name = wrapped.group(2)
        found.append((index, level, name))
    return found


def section_bodies(text: str, names: list[str]) -> dict[str, str]:
    """Map each heading's text, at its first occurrence, to its body."""

    text = text.replace(ENDING, "")
    lines, found = text.splitlines(), headings(text)
    outside = _unfenced(lines)
    setext = {index - 1 for index, _, _ in found if not _HEADING.match(lines[index])}
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
        bodies.setdefault(
            name,
            "\n".join(
                lines[i]
                for i in range(index + 1, end)
                if outside[i] and i not in setext
            ),
        )
    return bodies


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return set(zip(*(words[k:] for k in range(4)), strict=False))


def passes(
    requirement: dict[str, Any], text: str, names: list[str], turn1: str = ""
) -> bool:
    """Return whether ``text`` satisfies one requirement of an item.

    ``names`` are the item's sections, which bound each other's bodies, and
    ``turn1`` is the turn-1 output that a removal's content comes from.
    """

    kind = requirement["kind"]
    if kind == "ending":
        return text.rstrip().endswith(ENDING)
    found = [name for _, _, name in headings(text)]
    if kind == "absent":
        removed = requirement["section"].casefold()
        bold = [
            m.group(2) for line in text.splitlines() if (m := _BOLD_LINE.match(line))
        ]
        if any(name.strip().casefold() == removed for name in found + bold):
            return False
        before = _shingles(section_bodies(turn1, names).get(requirement["section"], ""))
        kept = before & _shingles(text)
        return not before or len(kept) <= SURVIVAL * len(before)
    if kind == "headings":
        wanted = requirement["sections"]
        return [name for name in dict.fromkeys(found) if name in wanted] == wanted
    body = section_bodies(text, names).get(requirement["section"])
    if body is None:
        return False
    if kind == "bullets":
        count = sum(
            bool(_BULLET.match(line)) and not _BREAK.match(line)
            for line in body.splitlines()
        )
        return count == requirement["count"]
    if kind == "paragraphs":
        blocks = [b for b in re.split(r"\n\s*\n", body) if b.strip()]
        return sum(not _HEADING.match(b.strip()) for b in blocks) >= 2

    tokens = Counter(re.findall(r"[a-z]+", body.lower()))

    def uses(word: str) -> int:
        return sum(tokens[form] for form in forms(word))

    absent = requirement.get("absent")
    return uses(requirement["word"]) >= 2 and not (absent and uses(absent))


def evaluate(item: dict[str, Any], turn1: str, final: str) -> dict[str, Any]:
    """Return incorporation, breaks, and locality for one run's two outputs."""

    names = item["sections"]
    before = {r["id"]: passes(r, turn1, names) for r in item["turn1"]}
    after = {r["id"]: passes(r, final, names, turn1) for r in item["turn2"]}
    kept = [i for i in before if i not in item["changed"] and before[i]]
    broken = [i for i in kept if not after[i]]
    bodies1, bodies2 = section_bodies(turn1, names), section_bodies(final, names)
    untargeted = [
        name
        for name in item["turn1"][0]["sections"]
        if name not in item["targets"] and name in bodies1
    ]
    ratios = {
        name: SequenceMatcher(
            None, " ".join(bodies1[name].split()), " ".join(bodies2[name].split())
        ).ratio()
        if name in bodies2
        else 0.0
        for name in untargeted
    }
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
        "untargeted_similarity": ratios,
        "mean_similarity": sum(ratios.values()) / len(ratios) if ratios else None,
    }


def assert_unexposed(run_dir: Path, items_path: Path, out: Path) -> None:
    """Refuse a run that could have seen the generator, checker, or items.

    The items file and the check's output must lie outside the run output
    root; the workspace must hold no copy of this module or the items file;
    and the run's harness records must not name the module path, the items
    path, or the items file's hash.
    """

    root = run_dir.resolve().parents[3]
    for path in (items_path, out):
        if path.resolve().is_relative_to(root):
            raise RuntimeError(f"{path} lies inside the run output root {root}")
    module, items = Path(__file__).resolve(), items_path.resolve()
    digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in (module, items)}
    for path in (run_dir / "workspace").rglob("*"):
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() in digests:
            raise RuntimeError(f"{path} copies a generator or checker file")
    needles = [str(module).encode(), str(items).encode()]
    needles.append(hashlib.sha256(items.read_bytes()).hexdigest().encode())
    records = [*run_dir.glob("attempt-*.events.jsonl"), *run_dir.glob("sessions/**/*")]
    for path in records:
        if path.is_file() and any(needle in path.read_bytes() for needle in needles):
            raise RuntimeError(f"{path} names a generator or checker file")


def check(
    items_path: Path,
    item_id: str,
    run_dir: Path,
    out: Path,
    turn1: Path | None = None,
) -> dict[str, Any]:
    """Check one run's final output against an item and write the result to ``out``.

    ``turn1`` defaults to the run's ``turn1/output.normalized.txt`` snapshot.
    """

    assert_unexposed(run_dir, items_path, out)
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
    result["run_dir"] = str(run_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate").add_argument("--out", type=Path, required=True)
    checker = commands.add_parser("check")
    checker.add_argument("--items", type=Path, required=True)
    checker.add_argument("--item", required=True, help="an item id, such as p.term")
    checker.add_argument(
        "--out", type=Path, required=True, help="result file outside the output root"
    )
    checker.add_argument(
        "--turn1", type=Path, default=None, help="turn-1 output, if not the run's"
    )
    checker.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "generate":
        generate(args.out)
    else:
        result = check(args.items, args.item, args.run_dir, args.out, args.turn1)
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
