"""Platform-specific headless command adapters."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


@dataclass(frozen=True)
class PlatformAdapter:
    """Build argv lists without invoking a shell or an interactive fallback."""

    platform: str
    executable: str
    first_args: tuple[str, ...]
    continuation_args: tuple[str, ...]
    version_args: tuple[str, ...]
    prompt_mode: str
    runtime_args: tuple[str, ...]
    network_enforcement: str
    control_status: tuple[tuple[str, str], ...]

    CONTROL_NAMES = frozenset(
        {
            "maximum_output_tokens",
            "temperature",
            "top_p_or_equivalent",
            "generation_seed",
            "stop_rules",
        }
    )

    @classmethod
    def load(cls, path: Path) -> PlatformAdapter:
        """Load one frozen adapter definition from TOML."""

        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(
                f"Cannot read platform adapter {path}: {exc}"
            ) from exc
        required = (
            "platform",
            "executable",
            "first_args",
            "continuation_args",
            "version_args",
        )
        missing = [field for field in required if field not in data]
        if missing:
            raise ConfigurationError(f"Adapter {path} is missing: {', '.join(missing)}")
        adapter = cls(
            platform=str(data["platform"]),
            executable=str(data["executable"]),
            first_args=tuple(str(item) for item in data["first_args"]),
            continuation_args=tuple(str(item) for item in data["continuation_args"]),
            version_args=tuple(str(item) for item in data["version_args"]),
            prompt_mode=str(data.get("prompt_mode", "argument")),
            runtime_args=tuple(str(item) for item in data.get("runtime_args", [])),
            network_enforcement=str(data.get("network_enforcement", "monitored-only")),
            control_status=tuple(
                (str(key), str(value))
                for key, value in data.get("control_status", {}).items()
            ),
        )
        adapter.validate_templates()
        return adapter

    def validate_templates(self) -> None:
        """Reject adapters that could silently invoke an interactive CLI."""

        if self.platform == "codex-primary":
            if self.first_args[:1] != ("exec",) or "--json" not in self.first_args:
                raise ConfigurationError("Codex adapter must use codex exec --json")
            if 'approval_policy="never"' not in self.runtime_args:
                raise ConfigurationError(
                    'Codex adapter must set approval_policy="never" via --config'
                )
            if "workspace-write" not in self.first_args:
                raise ConfigurationError("Codex adapter must allow plugin trace writes")
            if self.continuation_args[:2] != ("exec", "resume"):
                raise ConfigurationError(
                    "Codex continuation must use codex exec resume"
                )
        elif self.platform == "claude-code-replication":
            if "--print" not in self.first_args:
                raise ConfigurationError("Claude adapter must use claude --print")
            if "Read,Write,Edit" not in self.first_args:
                raise ConfigurationError(
                    "Claude adapter must allow plugin trace writes"
                )
            if "--resume" not in self.continuation_args:
                raise ConfigurationError("Claude continuation must use --resume")
        else:
            raise ConfigurationError(f"Unknown adapter platform: {self.platform}")
        if self.prompt_mode not in {"argument", "stdin"}:
            raise ConfigurationError("Adapter prompt_mode must be argument or stdin")
        if self.network_enforcement not in {"enforced", "monitored-only"}:
            raise ConfigurationError(
                "Adapter network_enforcement must be enforced or monitored-only"
            )
        if not self.runtime_args:
            raise ConfigurationError("Adapter must define runtime_args")
        statuses = self.control_status_dict
        missing_controls = self.CONTROL_NAMES - statuses.keys()
        if missing_controls:
            raise ConfigurationError(
                "Adapter must declare control status for: "
                + ", ".join(sorted(missing_controls))
            )
        invalid_statuses = {
            value
            for value in statuses.values()
            if value not in {"enforced", "monitored-only"}
        }
        if invalid_statuses:
            raise ConfigurationError(
                "Adapter control statuses must be enforced or monitored-only"
            )

    @property
    def control_status_dict(self) -> dict[str, str]:
        """Return the adapter's enforcement status for each runtime control."""

        return dict(self.control_status)

    def build_command(
        self,
        *,
        model_id: str,
        prompt: str,
        session_id: str | None = None,
        plugin_dirs: tuple[str, ...] = (),
        runtime_values: Mapping[str, Any] | None = None,
        output_budget_tokens: int | None = None,
        decoding: Mapping[str, Any] | None = None,
    ) -> list[str]:
        """Build a single non-interactive command for a first or next turn."""

        templates = self.first_args if session_id is None else self.continuation_args
        values: dict[str, Any] = {
            "model_id": model_id,
            "session_id": session_id or "",
        }
        if runtime_values:
            values.update(runtime_values)
        if output_budget_tokens is not None:
            values["maximum_output_tokens"] = output_budget_tokens
        if decoding:
            values.update(decoding)
        args = [_render(item, values) for item in templates]
        args.extend(_render(item, values) for item in self.runtime_args)
        if self.platform == "claude-code-replication":
            for plugin_dir in plugin_dirs:
                args.extend(("--plugin-dir", plugin_dir))
        if self.prompt_mode == "argument":
            args.append(prompt)
        return [self.executable, *args]

    def probe_version(self, *, timeout_seconds: float) -> str:
        """Read the installed CLI version before the first model turn."""

        try:
            result = subprocess.run(
                [self.executable, *self.version_args],
                capture_output=True,
                check=True,
                text=True,
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConfigurationError(
                f"Cannot validate installed {self.platform} CLI "
                f"{self.executable}: {exc}"
            ) from exc
        version = (result.stdout or result.stderr).strip()
        if not version:
            raise ConfigurationError(f"{self.executable} returned an empty version")
        return version


def _render(template: str, values: Mapping[str, Any]) -> str:
    """Render named adapter placeholders without interpreting JSON braces."""

    def replacement(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise ConfigurationError(
                f"Adapter template contains an unknown placeholder: {key}"
            )
        value = values[key]
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        elif isinstance(value, bool):
            return str(value).lower()
        else:
            return str(value)

    rendered = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", replacement, template)
    if re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", rendered):
        raise ConfigurationError(
            f"Adapter template contains an unresolved placeholder: {template}"
        )
    return rendered
