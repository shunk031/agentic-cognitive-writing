"""Errors raised by the judge client and scorer."""


class JudgeError(Exception):
    """Base class for judge-stage failures."""


class JudgeConfigurationError(JudgeError):
    """A judge configuration is missing or invalid."""


class JudgeTransportError(JudgeError):
    """The OpenAI-compatible endpoint did not return a usable response."""

    MAX_RESPONSE_BODY_LENGTH = 4096

    def __init__(self, message: str, *, response_body: str | None = None) -> None:
        self.response_body = (
            response_body[: self.MAX_RESPONSE_BODY_LENGTH]
            if response_body is not None
            else None
        )
        if self.response_body:
            message = f"{message}: {self.response_body}"
        super().__init__(message)


class JudgeValidationError(JudgeError):
    """A judge response does not satisfy the frozen JSON contract."""


class RunArtifactError(JudgeError):
    """A completed runner artifact is missing or cannot be scored."""
