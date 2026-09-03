"""Versioned, deterministic judge-template loading and rendering."""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..runner.hashing import sha256_bytes
from .errors import JudgeConfigurationError


def _prompt_body(text: str) -> str:
    """Remove only leading comment header lines from a prompt file."""

    lines = text.splitlines()
    index = 0
    while index < len(lines) and (
        not lines[index].strip() or lines[index].startswith("#")
    ):
        index += 1
    body = "\n".join(lines[index:])
    if text.endswith("\n"):
        body += "\n"
    if not body.strip():
        raise JudgeConfigurationError("Judge prompt template has no prompt body")
    return body


@dataclass(frozen=True)
class JudgeTemplate:
    """A raw, hashed prompt file with an explicit replacement field set."""

    path: Path
    raw: bytes
    body: str
    sha256: str
    fields: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> JudgeTemplate:
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise JudgeConfigurationError(
                f"Cannot read judge prompt template {path}: {exc}"
            ) from exc
        body = _prompt_body(text)
        formatter = string.Formatter()
        fields: list[str] = []
        try:
            parsed = formatter.parse(body)
            for _literal, field_name, format_spec, conversion in parsed:
                if field_name is None:
                    continue
                if (
                    not field_name.isidentifier()
                    or format_spec
                    or conversion is not None
                ):
                    raise JudgeConfigurationError(
                        "Judge templates allow only simple named replacement fields"
                    )
                if field_name not in fields:
                    fields.append(field_name)
        except ValueError as exc:
            raise JudgeConfigurationError(
                f"Judge prompt template has invalid interpolation syntax: {path}"
            ) from exc
        return cls(
            path=path,
            raw=raw,
            body=body,
            sha256=sha256_bytes(raw),
            fields=tuple(fields),
        )

    def render(self, values: dict[str, Any]) -> str:
        """Render exactly the declared fields and reject hidden substitutions."""

        missing = [field for field in self.fields if field not in values]
        if missing:
            raise JudgeConfigurationError(
                "Judge prompt template fields are missing values: " + ", ".join(missing)
            )
        unknown = [field for field in values if field not in self.fields]
        if unknown:
            raise JudgeConfigurationError(
                "Judge prompt template does not declare values: " + ", ".join(unknown)
            )
        try:
            return string.Formatter().vformat(self.body, (), values)
        except (KeyError, ValueError) as exc:
            raise JudgeConfigurationError(
                f"Cannot render judge prompt template {self.path}: {exc}"
            ) from exc
