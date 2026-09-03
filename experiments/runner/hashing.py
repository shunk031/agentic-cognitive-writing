"""Content hashing used by prompt and run manifests."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> bytes:
    """Serialize JSON deterministically for content-addressed artifacts."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    """Return a hexadecimal SHA-256 digest for bytes."""

    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    """Return a SHA-256 digest of canonical JSON."""

    return sha256_bytes(canonical_json(value))


def sha256_file(path) -> str:
    """Return a SHA-256 digest without changing the file bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
