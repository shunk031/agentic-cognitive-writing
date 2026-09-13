"""Download pinned benchmark sources and build immutable prompt manifests."""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_cogwriter.paths import BENCHMARK_CACHE_DIR, MANIFESTS_DIR
from agentic_cogwriter.runner.hashing import (
    canonical_json,
    sha256_bytes,
    sha256_file,
    sha256_json,
)

DEFAULT_OUTPUT_DIR = MANIFESTS_DIR
DEFAULT_CACHE_DIR = BENCHMARK_CACHE_DIR

WRITINGBENCH_COMMIT = "9c24bb67fd7451a2eacf5810aa7721e3a8b3bdad"
WRITINGBENCH_BLOB_SHA1 = "e6cd82aabed6fa845f0a28cd2114daad59c012b9"
HELLOBENCH_COMMIT = "92c7d469230b5b6b6ee1bfc1ea2ce49cb9125b57"
DOLOMITES_COMMIT = "8331dd998bf510cacc58d10ad613c9e685787747"
HABERMAS_COMMIT = "7923b71966c14136077c78d7841bc9e1a182dfe0"
HABERMAS_DEFAULT_COUNT = 10
HABERMAS_SEED = 20260908
HABERMAS_LIKERT_MIDPOINT = 4
HABERMAS_LIKERT_VALUES = {
    "STRONGLY_DISAGREE": 1,
    "DISAGREE": 2,
    "SOMEWHAT_DISAGREE": 3,
    "NEUTRAL": 4,
    "SOMEWHAT_AGREE": 5,
    "AGREE": 6,
    "STRONGLY_AGREE": 7,
}
HABERMAS_ASSIGNMENT = (
    "A group of participants answered the question with the opinions supplied. "
    "Write a statement the group could endorse."
)
HABERMAS_OUTPUT_CONSTRAINT = "No separate output constraints; follow prompt_text."
HABERMAS_MISSING_OPINION = "No opinion was provided."
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
HABERMAS_CANDIDATE_COMPARISONS_URL = (
    "https://storage.googleapis.com/habermas_machine/datasets/"
    "hm_all_candidate_comparisons.parquet"
)
HABERMAS_POSITION_STATEMENT_RATINGS_URL = (
    "https://storage.googleapis.com/habermas_machine/datasets/"
    "hm_all_position_statement_ratings.parquet"
)

MANIFEST_FIELDS = (
    "prompt_id",
    "benchmark_name",
    "source_version",
    "prompt_text",
    "requested_output_constraints",
    "hash",
)
# Native evaluator payloads are optional at the manifest schema level and are
# validated against the named benchmark below.
WRITINGBENCH_MANIFEST_FIELDS = (*MANIFEST_FIELDS[:-1], "native_payload", "hash")
HELLOBENCH_MANIFEST_FIELDS = WRITINGBENCH_MANIFEST_FIELDS
HABERMAS_MANIFEST_FIELDS = (*MANIFEST_FIELDS[:-1], "supplied_context", "hash")

EXPECTED_COUNTS = {
    "writingbench": 1000,
    "hellobench": 647,
    "dolomites": 820,
    "habermas": HABERMAS_DEFAULT_COUNT,
}

BENCHMARKS = tuple(EXPECTED_COUNTS)

DOLOMITES_DEV_MEMBER = "dolomites_examples/dolomites_examples.dev.public.jsonl"
DOLOMITES_TEST_MEMBER = "dolomites_examples/dolomites_examples.test.noreference.jsonl"

HABERMAS_CANDIDATE_FIELDS = (
    "question.id",
    "question.text",
    "question.split",
    "launch_id",
    "round_id",
    "iteration_index",
    "own_opinion.metadata.participant_id",
    "own_opinion.text",
    "own_opinion.metadata.status",
)
HABERMAS_RATING_FIELDS = (
    "question.id",
    "launch_id",
    "metadata.participant_id",
    "ratings.agreement",
)


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

HABERMAS_FILES = (
    RemoteFile(
        "habermas-machine-hm_all_candidate_comparisons.parquet",
        HABERMAS_CANDIDATE_COMPARISONS_URL,
        "7cf8d5ce3fce8853b36f0ffe1158424f7813867e422e313db4df0a5f9e03e4a4",
    ),
    RemoteFile(
        "habermas-machine-hm_all_position_statement_ratings.parquet",
        HABERMAS_POSITION_STATEMENT_RATINGS_URL,
        "b6debcb3e2413d26b7e8b96c7927517b7a5f304c502c30b28a9af1d307255763",
    ),
)
HABERMAS_CANDIDATE_FILE, HABERMAS_RATINGS_FILE = HABERMAS_FILES


def pretty_json(value: Any) -> str:
    """Serialize a plain JSON document in the checked-in data-file format."""

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def hash_manifest_row(row: dict[str, Any]) -> str:
    """Hash all manifest fields except the self-referential ``hash`` field."""

    unhashed = {key: value for key, value in row.items() if key != "hash"}
    return sha256_json(unhashed)


def validate_manifest_row(row: dict[str, Any]) -> None:
    """Validate one row against the experiment prompt-manifest contract."""

    if set(row) not in (
        set(MANIFEST_FIELDS),
        set(WRITINGBENCH_MANIFEST_FIELDS),
        set(HABERMAS_MANIFEST_FIELDS),
    ):
        raise ValueError(f"manifest fields are invalid, got {sorted(row)!r}")
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
    if row["benchmark_name"] == "WritingBench":
        if set(row) != set(WRITINGBENCH_MANIFEST_FIELDS):
            raise ValueError(
                "WritingBench rows must include the native_payload checklist"
            )
        native_payload = row["native_payload"]
        required_checklist_fields = {
            "name",
            "criteria_description",
            "1-2",
            "3-4",
            "5-6",
            "7-8",
            "9-10",
        }
        if not isinstance(native_payload, list) or not native_payload:
            raise ValueError("WritingBench native_payload must be a non-empty list")
        for criterion in native_payload:
            if (
                not isinstance(criterion, dict)
                or set(criterion) != required_checklist_fields
            ):
                raise ValueError("WritingBench checklist criterion fields are invalid")
            if not all(
                isinstance(value, str) and value.strip() for value in criterion.values()
            ):
                raise ValueError(
                    "WritingBench checklist values must be non-empty strings"
                )
    elif row["benchmark_name"] == "HelloBench":
        if set(row) != set(HELLOBENCH_MANIFEST_FIELDS):
            raise ValueError(
                "HelloBench rows must include the native_payload checklist"
            )
        native_payload = row["native_payload"]
        if not isinstance(native_payload, list) or not native_payload:
            raise ValueError("HelloBench native_payload must be a non-empty list")
        if not all(isinstance(item, str) and item.strip() for item in native_payload):
            raise ValueError("HelloBench native_payload must contain non-empty strings")
    elif row["benchmark_name"] == "HabermasMachine":
        if set(row) != set(HABERMAS_MANIFEST_FIELDS):
            raise ValueError(
                "HabermasMachine rows must include supplied_context and omit "
                "native_payload"
            )
        if (
            not isinstance(row["supplied_context"], str)
            or not row["supplied_context"].strip()
        ):
            raise ValueError("HabermasMachine supplied_context must be non-empty")
    elif "native_payload" in row:
        raise ValueError(
            "native_payload is only supported for WritingBench and HelloBench rows"
        )
    elif "supplied_context" in row:
        raise ValueError("supplied_context is only supported for HabermasMachine rows")
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
    observed = sha256_bytes(content)
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
    native_payload: list[dict[str, Any]] | None = None,
    supplied_context: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "prompt_id": prompt_id,
        "benchmark_name": benchmark_name,
        "source_version": source_version,
        "prompt_text": prompt_text,
        "requested_output_constraints": requested_output_constraints,
    }
    if native_payload is not None:
        row["native_payload"] = native_payload
    if supplied_context is not None:
        row["supplied_context"] = supplied_context
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
        encoded_rows.append(canonical_json(row) + b"\n")
    return b"".join(encoded_rows)


def _write_manifest(
    output_dir: Path,
    name: str,
    rows: list[dict[str, Any]],
    *,
    expected_count: int | None = None,
) -> Path:
    expected = EXPECTED_COUNTS[name] if expected_count is None else expected_count
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
                source_version=(
                    f"X-PLUG/WritingBench@{WRITINGBENCH_COMMIT}; "
                    f"benchmark_query/benchmark_all.jsonl blob:{WRITINGBENCH_BLOB_SHA1}"
                ),
                prompt_text=source_row["query"],
                requested_output_constraints=[
                    "Follow all task, language, audience, format, style, length, and "
                    "content constraints embedded in prompt_text."
                ],
                native_payload=source_row["checklist"],
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
            checklists = source_row.get("checklists")
            if (
                not isinstance(checklists, list)
                or not checklists
                or not all(
                    isinstance(item, str) and item.strip() for item in checklists
                )
            ):
                raise ValueError(f"HelloBench checklists are invalid for {source_id}")
            if not isinstance(source_row.get("formatted_checklists"), str) or not (
                source_row["formatted_checklists"].strip()
            ):
                raise ValueError(
                    f"HelloBench formatted_checklists are invalid for {source_id}"
                )
            num_checklist = source_row.get("num_checklist")
            if (
                isinstance(num_checklist, bool)
                or not isinstance(num_checklist, int)
                or num_checklist != len(checklists)
            ):
                raise ValueError(f"HelloBench num_checklist is invalid for {source_id}")
            if not constraints:
                constraints = ["No separate output constraints; follow prompt_text."]
            rows.append(
                _manifest_row(
                    prompt_id=f"hellobench-{source_id}",
                    benchmark_name="HelloBench",
                    source_version=f"Quehry/HelloBench@{HELLOBENCH_COMMIT}",
                    prompt_text=prompt_text,
                    requested_output_constraints=constraints,
                    native_payload=checklists,
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


def _read_parquet_rows(path: Path, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise RuntimeError(
            "HabermasMachine materialization requires the pyarrow dependency"
        ) from exc

    available = set(parquet.read_schema(path).names)
    missing = [field for field in fields if field not in available]
    if missing:
        raise ValueError(
            f"HabermasMachine source {path} is missing fields: {', '.join(missing)}"
        )
    return parquet.read_table(path, columns=list(fields)).to_pylist()


def _habermas_value(value: Any, field: str) -> str:
    if value is None:
        raise ValueError(f"HabermasMachine {field} must not be null")
    value = value.item() if hasattr(value, "item") else value
    text = str(value)
    if not text:
        raise ValueError(f"HabermasMachine {field} must not be empty")
    return text


def _is_ood_test(value: Any) -> bool:
    return value == "OOD_TEST" or value == 4


def _short_launch_id(launch_id: str) -> str:
    return launch_id[:8]


def _format_habermas_opinion(opinion: str) -> str:
    return opinion.replace("\n", "\n   ")


def build_habermas(
    candidate_comparisons_path: Path,
    position_statement_ratings_path: Path,
    *,
    count: int = HABERMAS_DEFAULT_COUNT,
    seed: int = HABERMAS_SEED,
) -> list[dict[str, Any]]:
    """Select disagreement groups and build Habermas Machine prompt rows."""

    if count < 1:
        raise ValueError("HabermasMachine count must be positive")

    candidate_rows = _read_parquet_rows(
        candidate_comparisons_path, HABERMAS_CANDIDATE_FIELDS
    )
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source_row in candidate_rows:
        if not _is_ood_test(source_row["question.split"]):
            continue
        if source_row["iteration_index"] != 0:
            continue
        question_id = _habermas_value(source_row["question.id"], "question.id")
        launch_id = _habermas_value(source_row["launch_id"], "launch_id")
        round_id = _habermas_value(source_row["round_id"], "round_id")
        key = (question_id, launch_id, round_id)
        group = groups.setdefault(
            key,
            {
                "question_text": source_row["question.text"],
                "opinions": {},
                "invalid_opinion": False,
            },
        )
        participant_id = _habermas_value(
            source_row["own_opinion.metadata.participant_id"],
            "own_opinion.metadata.participant_id",
        )
        opinion = source_row["own_opinion.text"]
        status = _habermas_value(
            source_row["own_opinion.metadata.status"],
            "own_opinion.metadata.status",
        )
        if (
            status != "COMPLETED"
            or not isinstance(opinion, str)
            or not opinion.strip()
            or opinion == HABERMAS_MISSING_OPINION
        ):
            group["invalid_opinion"] = True
            continue
        group["opinions"][participant_id] = opinion

    rating_rows = _read_parquet_rows(
        position_statement_ratings_path, HABERMAS_RATING_FIELDS
    )
    ratings: dict[tuple[str, str], list[Any]] = {}
    participant_order: dict[tuple[str, str], list[str]] = {}
    for source_row in rating_rows:
        question_id = _habermas_value(source_row["question.id"], "question.id")
        launch_id = _habermas_value(source_row["launch_id"], "launch_id")
        participant_id = _habermas_value(
            source_row["metadata.participant_id"], "metadata.participant_id"
        )
        agreement = source_row["ratings.agreement"]
        if not isinstance(agreement, list) or len(agreement) != 1:
            continue
        agreement_name = agreement[0]
        if agreement_name not in HABERMAS_LIKERT_VALUES:
            continue
        key = (question_id, launch_id)
        ratings.setdefault(key, []).append(HABERMAS_LIKERT_VALUES[agreement_name])
        if participant_id not in participant_order.setdefault(key, []):
            participant_order[key].append(participant_id)

    eligible: list[tuple[tuple[str, str, str], str, str]] = []
    for key in sorted(groups):
        question_id, launch_id, round_id = key
        group = groups[key]
        if group["invalid_opinion"]:
            continue
        opinions = group["opinions"]
        if len(opinions) != 5 or len(set(opinions.values())) != 5:
            continue
        question_text = group["question_text"]
        if not isinstance(question_text, str) or not question_text.strip():
            continue
        group_ratings = ratings.get((question_id, launch_id), [])
        numeric_ratings = [
            float(value)
            for value in group_ratings
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if not (
            any(value < HABERMAS_LIKERT_MIDPOINT for value in numeric_ratings)
            and any(value > HABERMAS_LIKERT_MIDPOINT for value in numeric_ratings)
        ):
            continue
        ordered_participants = participant_order.get((question_id, launch_id), [])
        if len(ordered_participants) != 5 or any(
            participant not in opinions for participant in ordered_participants
        ):
            continue
        ordered_opinions = [
            opinions[participant] for participant in ordered_participants
        ]
        eligible.append(
            (
                key,
                question_text,
                "\n".join(
                    f"{index}. {_format_habermas_opinion(opinion)}"
                    for index, opinion in enumerate(ordered_opinions, start=1)
                ),
            )
        )

    if count > len(eligible):
        raise ValueError(
            f"requested {count} HabermasMachine groups, but only "
            f"{len(eligible)} meet the selection criterion"
        )
    eligible.sort(key=lambda item: item[0])
    selected = random.Random(seed).sample(eligible, count)
    selected.sort(key=lambda item: item[0])
    rows = []
    for (question_id, launch_id, _), question_text, supplied_context in selected:
        rows.append(
            _manifest_row(
                prompt_id=f"habermas-{question_id}-{_short_launch_id(launch_id)}",
                benchmark_name="HabermasMachine",
                source_version=f"google-deepmind/habermas_machine@{HABERMAS_COMMIT}",
                prompt_text=f"{HABERMAS_ASSIGNMENT}\n\n### Question\n{question_text}",
                requested_output_constraints=[HABERMAS_OUTPUT_CONSTRAINT],
                supplied_context=supplied_context,
            )
        )
    return rows


def provenance(
    observed_dolomites_counts: dict[str, int],
    *,
    habermas_count: int = HABERMAS_DEFAULT_COUNT,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "manifest_hash": "sha256(canonical JSON row without hash)",
        "benchmarks": {
            "writingbench": {
                "name": "WritingBench",
                "repository": "https://github.com/X-PLUG/WritingBench",
                "source_version": (
                    f"X-PLUG/WritingBench@{WRITINGBENCH_COMMIT}; "
                    f"benchmark_query/benchmark_all.jsonl blob:{WRITINGBENCH_BLOB_SHA1}"
                ),
                "source_file": "benchmark_query/benchmark_all.jsonl",
                "source_url": WRITINGBENCH_URL,
                "source_sha256": WRITINGBENCH_FILE.sha256,
                "source_blob_sha1": WRITINGBENCH_BLOB_SHA1,
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
                "native_payload": {
                    "source_fields": [
                        "checklists",
                        "formatted_checklists",
                        "num_checklist",
                    ],
                    "manifest_field": "native_payload",
                    "shape": "non-empty list of non-empty strings",
                },
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
            "habermas": {
                "name": "HabermasMachine",
                "repository": (
                    "https://github.com/google-deepmind/habermas_machine/tree/"
                    f"{HABERMAS_COMMIT}"
                ),
                "source_version": (
                    f"google-deepmind/habermas_machine@{HABERMAS_COMMIT}"
                ),
                "source_files": [
                    {
                        "path": source.cache_name,
                        "url": source.url,
                        "sha256": source.sha256,
                    }
                    for source in HABERMAS_FILES
                ],
                "source_fields": {
                    "candidate_comparisons": list(HABERMAS_CANDIDATE_FIELDS),
                    "position_statement_ratings": list(HABERMAS_RATING_FIELDS),
                },
                "license": "CC-BY-4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "citation": (
                    "Tessler et al., AI can help humans find common ground in "
                    "democratic deliberation, Science 386(6719), 2024, "
                    "https://doi.org/10.1126/science.adq2852"
                ),
                "attribution": (
                    "Tessler et al., AI can help humans find common ground in "
                    "democratic deliberation, Science 386(6719), 2024, "
                    "https://doi.org/10.1126/science.adq2852; Google DeepMind "
                    "Habermas Machine other materials, CC BY 4.0 "
                    "(https://creativecommons.org/licenses/by/4.0/). Changes: "
                    "selected OOD_TEST deliberation groups and converted their "
                    "five participant opinions into supplied context."
                ),
                "redistribution": (
                    "Prompt manifest only, with attribution above; source files "
                    "are acquired by the script."
                ),
                "manifest": "manifests/habermas.jsonl",
                "item_count": habermas_count,
                "selection": {
                    "split": "OOD_TEST",
                    "seed": HABERMAS_SEED,
                    "count": habermas_count,
                    "criterion": (
                        "questions from the OOD_TEST split; groups at "
                        "iteration_index 0 whose five own_opinion.text values are "
                        "all distinct and non-empty; disagreement measured from "
                        "hm_all_position_statement_ratings as the participants of "
                        "that launch having ratings.agreement values on both sides "
                        "of the scale's midpoint for that question"
                    ),
                    "sampling": (
                        "sort the full (question_id, launch_id, round_id) key "
                        "before seeded sampling"
                    ),
                    "likert_midpoint": HABERMAS_LIKERT_MIDPOINT,
                    "participant_order": (
                        "first occurrence of each participant in the ratings file"
                    ),
                    "missing_opinion_gate": (
                        "Every group member must have "
                        "own_opinion.metadata.status COMPLETED and "
                        "own_opinion.text must not equal "
                        "'No opinion was provided.'"
                    ),
                },
                "manifest_fields": {
                    "supplied_context": "numbered original participant opinions",
                    "native_payload": "omitted",
                },
            },
        },
    }


def _write_json(path: Path, value: Any) -> None:
    write_immutable(path, (pretty_json(value) + "\n").encode("utf-8"))


def materialize(
    benchmarks: Iterable[str],
    output_dir: Path,
    cache_dir: Path,
    *,
    habermas_count: int = HABERMAS_DEFAULT_COUNT,
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

    if "habermas" in selected:
        candidate_path = acquire(HABERMAS_CANDIDATE_FILE, cache_dir)
        ratings_path = acquire(HABERMAS_RATINGS_FILE, cache_dir)
        rows = build_habermas(
            candidate_path,
            ratings_path,
            count=habermas_count,
            seed=HABERMAS_SEED,
        )
        _write_manifest(output_dir, "habermas", rows, expected_count=habermas_count)
        counts["habermas"] = len(rows)

    if set(selected) == set(BENCHMARKS):
        _write_json(
            output_dir.parent / "provenance.json",
            provenance(observed_split, habermas_count=habermas_count),
        )
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
    parser.add_argument(
        "--habermas-count",
        type=int,
        default=HABERMAS_DEFAULT_COUNT,
        help="number of HabermasMachine groups to sample",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    selected = BENCHMARKS if args.benchmark == "all" else (args.benchmark,)
    counts = materialize(
        selected,
        args.output_dir,
        args.cache_dir,
        habermas_count=args.habermas_count,
    )
    for benchmark_name, count in counts.items():
        print(f"{benchmark_name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
