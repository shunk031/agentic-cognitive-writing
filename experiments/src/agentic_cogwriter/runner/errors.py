"""Errors raised by the experiment runner."""


class RunnerError(RuntimeError):
    """Base class for fail-closed runner errors."""


class ConfigurationError(RunnerError):
    """The runtime gate is open or a configuration is invalid."""


class ManifestError(RunnerError):
    """A prompt or run manifest violates its schema or hash contract."""


class BudgetExceeded(RunnerError):
    """A condition attempted to consume more output budget than assigned."""


class RetrievalViolation(RunnerError):
    """A generator or judge produced evidence of an unpermitted retrieval."""

    def __init__(
        self,
        message: str,
        *,
        matched_pattern: str | None = None,
        matching_line: str | None = None,
        stream: str | None = None,
        artifact_source: str = "transport",
        payload: bytes = b"",
    ) -> None:
        self.matched_pattern = matched_pattern
        self.matching_line = matching_line
        self.stream = stream
        self.artifact_source = artifact_source
        self.payload = payload
        if matched_pattern is not None and matching_line is not None:
            message = (
                f"{message}; matched_pattern={matched_pattern!r}; "
                f"matching_line={matching_line!r}"
            )
        super().__init__(message)


class ExecutionError(RunnerError):
    """A headless command failed, timed out, or returned unusable output."""


class TokenAccountingError(ExecutionError):
    """Codex did not provide a complete, valid turn-usage record."""


class SpawnEventError(ExecutionError):
    """A Codex collaboration spawn event is malformed."""


class UnscoredRun(ExecutionError):
    """A run completed transport execution but cannot enter scoring."""


class TraceValidationError(ExecutionError):
    """A plugin trace is not valid for the selected condition."""
