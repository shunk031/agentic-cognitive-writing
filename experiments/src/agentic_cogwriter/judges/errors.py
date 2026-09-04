"""Errors raised by the judge client and scorer."""


class JudgeError(Exception):
    """Base class for judge-stage failures."""


class JudgeConfigurationError(JudgeError):
    """A judge configuration is missing or invalid."""


class JudgeTransportError(JudgeError):
    """The OpenAI-compatible endpoint did not return a usable response."""


class JudgeValidationError(JudgeError):
    """A judge response does not satisfy the frozen JSON contract."""


class RunArtifactError(JudgeError):
    """A completed runner artifact is missing or cannot be scored."""
