"""Platform-specific headless command adapters."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

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
        )
        adapter.validate_templates()
        return adapter

    def validate_templates(self) -> None:
        """Reject adapters that could silently invoke an interactive CLI."""

        if self.platform == "codex-primary":
            if self.first_args[:1] != ("exec",) or "--json" not in self.first_args:
                raise ConfigurationError("Codex adapter must use codex exec --json")
            if "never" not in self.first_args:
                raise ConfigurationError("Codex adapter must disable approval prompts")
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

    def build_command(
        self,
        *,
        model_id: str,
        prompt: str,
        session_id: str | None = None,
        plugin_dirs: tuple[str, ...] = (),
    ) -> list[str]:
        """Build a single non-interactive command for a first or next turn."""

        templates = self.first_args if session_id is None else self.continuation_args
        values = {"model_id": model_id, "session_id": session_id or ""}
        args = [item.format(**values) for item in templates]
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
