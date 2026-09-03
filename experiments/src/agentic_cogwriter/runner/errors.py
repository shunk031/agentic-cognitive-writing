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


class ExecutionError(RunnerError):
    """A headless command failed, timed out, or returned unusable output."""
