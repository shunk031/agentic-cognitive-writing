import pytest

import agentic_cogwriter.runner.runner as runner_module


@pytest.fixture(autouse=True)  # noqa: V103 - vulture cannot see autouse fixtures
def _bound_guidance_scan(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Keep the guidance guard off host directories above pytest's temp root."""

    monkeypatch.setattr(
        runner_module,
        "_GUIDANCE_SCAN_ROOT",
        tmp_path_factory.getbasetemp().resolve(),
    )
