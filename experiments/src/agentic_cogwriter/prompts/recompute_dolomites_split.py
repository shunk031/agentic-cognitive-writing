"""Recompute the DoLoMiTes development/test split from the pinned archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentic_cogwriter.paths import BENCHMARK_CACHE_DIR, DOLOMITES_SPLIT_PATH
from agentic_cogwriter.prompts.materialize import (
    DOLOMITES_ARCHIVE,
    DOLOMITES_COMMIT,
    acquire,
    dolomites_archive_counts,
    pretty_json,
    sha256_file,
    write_immutable,
)

SCRIPT_VERSION = "1.0.0"
DEFAULT_CACHE_DIR = BENCHMARK_CACHE_DIR
DEFAULT_OUTPUT = DOLOMITES_SPLIT_PATH


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    archive = args.archive or acquire(DOLOMITES_ARCHIVE, args.cache_dir)
    archive_sha256 = sha256_file(archive)
    if archive_sha256 != DOLOMITES_ARCHIVE.sha256:
        raise ValueError(
            f"archive hash mismatch: expected {DOLOMITES_ARCHIVE.sha256}, "
            f"observed {archive_sha256}"
        )
    counts = dolomites_archive_counts(archive)
    result = {
        "script_version": SCRIPT_VERSION,
        "repository": "https://github.com/google-deepmind/dolomites",
        "source_version": f"google-deepmind/dolomites@{DOLOMITES_COMMIT}",
        "archive_url": DOLOMITES_ARCHIVE.url,
        "archive_sha256": archive_sha256,
        "observed_counts": counts,
        "authoritative_split": "archive-derived",
        "manifest_subset": "dev",
    }
    write_immutable(args.output, (pretty_json(result) + "\n").encode("utf-8"))
    print(pretty_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
