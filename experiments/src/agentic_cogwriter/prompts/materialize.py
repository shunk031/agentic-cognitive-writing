"""Download pinned benchmark sources and build immutable prompt manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPERIMENTS_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_ROOT = EXPERIMENTS_ROOT / "prompts"
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = PROMPTS_ROOT / "manifests"
DEFAULT_CACHE_DIR = REPOSITORY_ROOT / ".cache" / "benchmarks"

WRITINGBENCH_COMMIT = "9c24bb67fd7451a2eacf5810aa7721e3a8b3bdad"
HELLOBENCH_COMMIT = "92c7d469230b5b6b6ee1bfc1ea2ce49cb9125b57"
DOLOMITES_COMMIT = "8331dd998bf510cacc58d10ad613c9e685787747"
DOLOMITES_ARCHIVE_SHA256 = (
    "62ee47b4cdf67d1efd7a21029384a929e3d66cab49989aab85ea3534b8b86c32"
)

WRITINGBENCH_URL = (
    "https://raw.githubusercontent.com/X-PLUG/WritingBench/"
    f"{WRITINGBENCH_COMMIT}/benchmark_query/benchmark_all.jsonl"
)
DOLOMITES_ARCHIVE_URL = (
    "https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip"
)

MANIFEST_FIELDS = (
    "prompt_id",
    "benchmark_name",
    "source_version",
    "prompt_text",
    "requested_output_constraints",
    "hash",
)

EXPECTED_COUNTS = {
    "writingbench": 1000,
    "hellobench": 647,
    "dolomites": 820,
}

BENCHMARKS = tuple(EXPECTED_COUNTS)

DOLOMITES_DEV_MEMBER = "dolomites_examples/dolomites_examples.dev.public.jsonl"
DOLOMITES_TEST_MEMBER = "dolomites_examples/dolomites_examples.test.noreference.jsonl"


@dataclass(frozen=True)
class RemoteFile:
    """A source file pinned by URL and content hash."""

    cache_name: str
    url: str
    sha256: str


HELLOBENCH_FILES = (
    RemoteFile(
        "hellobench-chat.jsonl",
        f"https://raw.githubusercontent.com/Quehry/HelloBench/{HELLOBENCH_COMMIT}/"
        "data/main_data/chat.jsonl",
        "04f7a75417ab50f245c226143fa4f7ad48849459ae65ab5b3d0fceda9d36eff6",
    ),
    RemoteFile(
        "hellobench-heuristic_text_generation.jsonl",
        f"https://raw.githubusercontent.com/Quehry/HelloBench/{HELLOBENCH_COMMIT}/"
        "data/main_data/heuristic_text_generation.jsonl",
        "2b4a61adb627d2b54fb0ac77c5de427e0a7aa523c6f37b812087382a378b165c",
    ),
    RemoteFile(
        "hellobench-open_ended_qa.jsonl",
        f"https://raw.githubusercontent.com/Quehry/HelloBench/{HELLOBENCH_COMMIT}/"
        "data/main_data/open_ended_qa.jsonl",
        "57e76a480395a65d000b6081c24b76b8d6940758e953e3ae5c20d4bec8b9c102",
    ),
    RemoteFile(
        "hellobench-summarization.jsonl",
        f"https://raw.githubusercontent.com/Quehry/HelloBench/{HELLOBENCH_COMMIT}/"
        "data/main_data/summarization.jsonl",
        "53d0c93465291593c16fdcf7741b5af533918e3089b994ae6a11e69a9530f5e2",
    ),
    RemoteFile(
        "hellobench-text_completion.jsonl",
        f"https://raw.githubusercontent.com/Quehry/HelloBench/{HELLOBENCH_COMMIT}/"
        "data/main_data/text_completion.jsonl",
        "01852f09ebdeb4f8fc352ea23fffb504923cd3ec64824e23d39b4caa8afc2c84",
    ),
)

WRITINGBENCH_FILE = RemoteFile(
    "writingbench-benchmark_all.jsonl",
    WRITINGBENCH_URL,
    "026e3f9482ff3474c802cd43f5cae9fd584e10d0848d3e0a152695434becbc98",
)

DOLOMITES_ARCHIVE = RemoteFile(
    "dolomites_examples.zip",
    DOLOMITES_ARCHIVE_URL,
    DOLOMITES_ARCHIVE_SHA256,
)


def canonical_json(value: Any) -> str:
    """Serialize JSON in the stable form used by manifest hashes."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_manifest_row(row: dict[str, Any]) -> str:
    """Hash all manifest fields except the self-referential ``hash`` field."""

    unhashed = {key: value for key, value in row.items() if key != "hash"}
    return hashlib.sha256(canonical_json(unhashed).encode("utf-8")).hexdigest()


def validate_manifest_row(row: dict[str, Any]) -> None:
    """Validate one row against the experiment prompt-manifest contract."""

    if set(row) != set(MANIFEST_FIELDS):
        raise ValueError(
            f"manifest fields must be {MANIFEST_FIELDS!r}, got {sorted(row)!r}"
        )
    for field in ("prompt_id", "benchmark_name", "source_version", "prompt_text"):
        if not isinstance(row[field], str) or not row[field]:
            raise ValueError(f"{field} must be a non-empty string")
    constraints = row["requested_output_constraints"]
    if not isinstance(constraints, list) or not all(
        isinstance(item, str) and item for item in constraints
    ):
        raise ValueError(
            "requested_output_constraints must be a list of non-empty strings"
        )
    if not isinstance(row["hash"], str) or len(row["hash"]) != 64:
        raise ValueError("hash must be a 64-character SHA-256 hex digest")
    if row["hash"] != hash_manifest_row(row):
        raise ValueError(f"hash mismatch for {row['prompt_id']}")


def write_immutable(path: Path, content: bytes) -> None:
    """Create a file, allowing only an identical repeat write thereafter."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f"refusing to change immutable file: {path}")
        return
    path.write_bytes(content)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def acquire(source: RemoteFile, cache_dir: Path) -> Path:
    """Download one pinned source into a verified local cache."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / source.cache_name
    if target.exists():
        observed = sha256_file(target)
        if observed != source.sha256:
            raise ValueError(
                f"cached source hash mismatch for {target}: expected {source.sha256}, "
                f"observed {observed}"
            )
        return target

    request = urllib.request.Request(
        source.url,
        headers={"User-Agent": "agentic-cognitive-writing-benchmark-materializer/1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    observed = _sha256_bytes(content)
    if observed != source.sha256:
        raise ValueError(
            f"downloaded source hash mismatch for {source.url}: expected "
            f"{source.sha256}, "
            f"observed {observed}"
        )
    target.write_bytes(content)
    return target


def _iter_jsonl_lines(lines: Iterable[bytes], source: str) -> Iterator[dict[str, Any]]:
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {source}:{line_number}") from exc
        if not isinstance(row, dict):
            raise TypeError(f"expected an object in {source}:{line_number}")
        yield row


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as source:
        return list(_iter_jsonl_lines(source, str(path)))


def _manifest_row(
    *,
    prompt_id: str,
    benchmark_name: str,
    source_version: str,
    prompt_text: str,
    requested_output_constraints: list[str],
) -> dict[str, Any]:
    row = {
        "prompt_id": prompt_id,
        "benchmark_name": benchmark_name,
        "source_version": source_version,
        "prompt_text": prompt_text,
        "requested_output_constraints": requested_output_constraints,
    }
    row["hash"] = hash_manifest_row(row)
    validate_manifest_row(row)
    return row


def _manifest_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    encoded_rows = []
    seen_ids: set[str] = set()
    for row in rows:
        validate_manifest_row(row)
        if row["prompt_id"] in seen_ids:
            raise ValueError(f"duplicate prompt ID: {row['prompt_id']}")
        seen_ids.add(row["prompt_id"])
        encoded_rows.append(canonical_json(row).encode("utf-8") + b"\n")
    return b"".join(encoded_rows)


def _write_manifest(output_dir: Path, name: str, rows: list[dict[str, Any]]) -> Path:
    expected = EXPECTED_COUNTS[name]
    if len(rows) != expected:
        raise ValueError(f"{name} expected {expected} rows, observed {len(rows)}")
    target = output_dir / f"{name}.jsonl"
    write_immutable(target, _manifest_bytes(rows))
    return target


def build_writingbench(source_path: Path) -> list[dict[str, Any]]:
    source_rows = _read_jsonl(source_path)
    rows = []
    for source_row in source_rows:
        index = source_row.get("index")
        if not isinstance(index, int):
            raise TypeError("WritingBench index must be an integer")
        rows.append(
            _manifest_row(
                prompt_id=f"writingbench-{index:04d}",
                benchmark_name="WritingBench",
                source_version=f"X-PLUG/WritingBench@{WRITINGBENCH_COMMIT}",
                prompt_text=source_row["query"],
                requested_output_constraints=[
                    "Follow all task, language, audience, format, style, length, and "
                    "content constraints embedded in prompt_text."
                ],
            )
        )
    return rows


def build_hellobench(source_paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    for source_path in source_paths:
        for source_row in _read_jsonl(source_path):
            source_id = source_row.get("id")
            prompt_text = source_row.get("instruction")
            constraints = source_row.get("requirements") or []
            if not isinstance(source_id, str) or not isinstance(prompt_text, str):
                raise TypeError(
                    f"HelloBench row in {source_path} has invalid id/instruction"
                )
            if not isinstance(constraints, list) or not all(
                isinstance(item, str) for item in constraints
            ):
                raise ValueError(f"HelloBench requirements are invalid for {source_id}")
            if not constraints:
                constraints = ["No separate output constraints; follow prompt_text."]
            rows.append(
                _manifest_row(
                    prompt_id=f"hellobench-{source_id}",
                    benchmark_name="HelloBench",
                    source_version=f"Quehry/HelloBench@{HELLOBENCH_COMMIT}",
                    prompt_text=prompt_text,
                    requested_output_constraints=constraints,
                )
            )
    return rows


def _archive_jsonl_rows(archive: zipfile.ZipFile, member: str) -> list[dict[str, Any]]:
    try:
        file_handle = archive.open(member)
    except KeyError as exc:
        raise ValueError(f"archive missing required member: {member}") from exc
    with file_handle:
        return list(_iter_jsonl_lines(file_handle, member))


def dolomites_archive_counts(archive_path: Path) -> dict[str, int]:
    """Count the two split members in the released archive."""

    with zipfile.ZipFile(archive_path) as archive:
        return {
            "dev": len(_archive_jsonl_rows(archive, DOLOMITES_DEV_MEMBER)),
            "test": len(_archive_jsonl_rows(archive, DOLOMITES_TEST_MEMBER)),
        }


def build_dolomites(archive_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    with zipfile.ZipFile(archive_path) as archive:
        counts = {
            "dev": len(_archive_jsonl_rows(archive, DOLOMITES_DEV_MEMBER)),
            "test": len(_archive_jsonl_rows(archive, DOLOMITES_TEST_MEMBER)),
        }
        if counts != {"dev": 820, "test": 1037}:
            raise ValueError(f"unexpected DoLoMiTes archive split: {counts}")
        source_rows = _archive_jsonl_rows(archive, DOLOMITES_DEV_MEMBER)

    source_version = (
        f"google-deepmind/dolomites@{DOLOMITES_COMMIT}; "
        f"dolomites_examples.zip sha256:{DOLOMITES_ARCHIVE_SHA256}"
    )
    rows = []
    for source_row in source_rows:
        task = source_row["task"]
        prompt_text = "\n\n".join(
            (
                f"Task objective:\n{task['task_objective']}",
                f"Task procedure/context:\n{task['task_procedure']}",
                f"Input specification:\n{task['task_input']}",
                f"Supplied input:\n{source_row['example_input']}",
            )
        )
        constraints = [
            value
            for value in (task["task_output"], task["task_notes"])
            if isinstance(value, str) and value
        ]
        constraints.append(
            "Use only the supplied task context and input; do not retrieve or rely "
            "on outside sources."
        )
        rows.append(
            _manifest_row(
                prompt_id=f"dolomites-{source_row['example_id']}",
                benchmark_name="DoLoMiTes",
                source_version=source_version,
                prompt_text=prompt_text,
                requested_output_constraints=constraints,
            )
        )
    return rows, counts


def provenance(observed_dolomites_counts: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "manifest_hash": "sha256(canonical JSON row without hash)",
        "benchmarks": {
            "writingbench": {
                "name": "WritingBench",
                "repository": "https://github.com/X-PLUG/WritingBench",
                "source_version": f"X-PLUG/WritingBench@{WRITINGBENCH_COMMIT}",
                "source_file": "benchmark_query/benchmark_all.jsonl",
                "source_url": WRITINGBENCH_URL,
                "source_sha256": WRITINGBENCH_FILE.sha256,
                "license": "Apache-2.0",
                "redistribution": (
                    "Prompt manifest only; source file is acquired by the script."
                ),
                "manifest": "manifests/writingbench.jsonl",
                "item_count": EXPECTED_COUNTS["writingbench"],
            },
            "hellobench": {
                "name": "HelloBench",
                "repository": "https://github.com/Quehry/HelloBench",
                "source_version": f"Quehry/HelloBench@{HELLOBENCH_COMMIT}",
                "source_files": [
                    {
                        "path": source.cache_name,
                        "url": source.url,
                        "sha256": source.sha256,
                    }
                    for source in HELLOBENCH_FILES
                ],
                "license": "MIT",
                "redistribution": (
                    "Prompt manifest only; source files are acquired by the script."
                ),
                "manifest": "manifests/hellobench.jsonl",
                "item_count": EXPECTED_COUNTS["hellobench"],
            },
            "dolomites": {
                "name": "DoLoMiTes",
                "repository": "https://github.com/google-deepmind/dolomites",
                "source_version": f"google-deepmind/dolomites@{DOLOMITES_COMMIT}",
                "archive_url": DOLOMITES_ARCHIVE_URL,
                "archive_sha256": DOLOMITES_ARCHIVE_SHA256,
                "license": "CC-BY-4.0",
                "attribution": (
                    "DeepMind Technologies Limited, DoLoMiTes: Domain-Specific "
                    "Long-Form Methodical Tasks; CC BY 4.0. Changes: transformed the "
                    "development "
                    "examples into prompt rows and omitted reference outputs."
                ),
                "redistribution": (
                    "Development prompt manifest only, with attribution above."
                ),
                "manifest": "manifests/dolomites.jsonl",
                "item_count": EXPECTED_COUNTS["dolomites"],
                "split": {
                    "observed_counts": observed_dolomites_counts,
                    "expected_from_archive": {"dev": 820, "test": 1037},
                    "manifest_subset": "dev",
                    "authoritative_count": "archive-derived",
                    "split_script": "recompute_dolomites_split.py",
                },
            },
        },
    }


def _write_json(path: Path, value: Any) -> None:
    write_immutable(path, (canonical_json(value) + "\n").encode("utf-8"))


def materialize(
    benchmarks: Iterable[str], output_dir: Path, cache_dir: Path
) -> dict[str, int]:
    selected = tuple(benchmarks)
    output_dir.mkdir(parents=True, exist_ok=True)
    observed_split = {"dev": 820, "test": 1037}
    counts: dict[str, int] = {}

    if "writingbench" in selected:
        rows = build_writingbench(acquire(WRITINGBENCH_FILE, cache_dir))
        _write_manifest(output_dir, "writingbench", rows)
        counts["writingbench"] = len(rows)

    if "hellobench" in selected:
        rows = build_hellobench(
            acquire(source, cache_dir) for source in HELLOBENCH_FILES
        )
        _write_manifest(output_dir, "hellobench", rows)
        counts["hellobench"] = len(rows)

    if "dolomites" in selected:
        archive_path = acquire(DOLOMITES_ARCHIVE, cache_dir)
        rows, observed_split = build_dolomites(archive_path)
        _write_manifest(output_dir, "dolomites", rows)
        counts["dolomites"] = len(rows)

    if set(selected) == set(BENCHMARKS):
        _write_json(output_dir.parent / "provenance.json", provenance(observed_split))
    return counts


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        choices=[*BENCHMARKS, "all"],
        default="all",
        help="benchmark to materialize (default: all)",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    selected = BENCHMARKS if args.benchmark == "all" else (args.benchmark,)
    counts = materialize(selected, args.output_dir, args.cache_dir)
    for benchmark_name, count in counts.items():
        print(f"{benchmark_name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
