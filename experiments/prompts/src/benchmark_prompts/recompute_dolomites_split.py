"""Recompute the DoLoMiTes development/test split from the pinned archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmark_prompts.materialize import (
    DEFAULT_CACHE_DIR,
    DOLOMITES_ARCHIVE,
    DOLOMITES_COMMIT,
    acquire,
    canonical_json,
    dolomites_archive_counts,
    sha256_file,
    write_immutable,
)

SCRIPT_VERSION = "1.0.0"
PROMPTS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROMPTS_ROOT / "dolomites_split.json"


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
    write_immutable(args.output, (canonical_json(result) + "\n").encode("utf-8"))
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
