import shutil
from pathlib import Path

import pytest

from agentic_cogwriter.paths import EXPERIMENTS_ROOT
from agentic_cogwriter.runner.conditions import CONDITION_IDS, load_condition_registry
from agentic_cogwriter.runner.errors import ConfigurationError

CONDITIONS_DIR = EXPERIMENTS_ROOT / "conditions"


def _copy_conditions(tmp_path: Path) -> Path:
    target = tmp_path / "conditions"
    shutil.copytree(CONDITIONS_DIR, target)
    return target


def test_registry_parses_stages_from_condition_wrappers() -> None:
    registry = load_condition_registry()

    assert set(registry) == set(CONDITION_IDS)
    a1_stages = registry["A1"].stages
    assert [stage.stage_id for stage in a1_stages] == ["single_shot"]
    assert a1_stages[0].path == CONDITIONS_DIR / "prompts" / "a1_single_shot.md"
    assert a1_stages[0].sha256 == (
        "99964b369a76d8cb88ec375cda4e553a5b993483ca05b14e46c3c3fb3d3014cf"
    )
    assert [stage.stage_id for stage in registry["A2"].stages] == [
        "pre_write",
        "write",
        "re_write",
    ]
    assert [stage.stage_id for stage in registry["A3"].stages] == [
        "task-decomposition",
        "task-execution",
        "task-revision",
    ]
    assert all(stage.path is None for stage in registry["A3"].stages)
    assert [stage.stage_id for stage in registry["B2"].stages] == [
        "perspective_discovery",
        "simulated_qa",
        "outline",
        "draft",
        "polish",
    ]
    assert all(
        stage.path is not None and stage.sha256 is not None
        for stage in registry["B2"].stages
    )
    for condition_id in ("A4", "A5", "A6", "B1"):
        stages = registry[condition_id].stages
        assert [stage.stage_id for stage in stages] == ["plugin_session"]
        assert stages[0].path is None
        assert stages[0].sha256 is None


def test_registry_keeps_wrapper_paths_and_families() -> None:
    registry = load_condition_registry()

    assert registry["A1"].plugin_config == CONDITIONS_DIR / "a1_baseline.toml"
    families = {
        condition_id: spec.analysis_family for condition_id, spec in registry.items()
    }
    assert families == {
        "A1": "confirmatory",
        "A2": "confirmatory",
        "A3": "confirmatory",
        "A4": "confirmatory",
        "A5": "confirmatory",
        "A6": "confirmatory",
        "B1": "exploratory",
        "B2": "exploratory",
    }


def test_missing_condition_wrapper_is_an_error(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    (conditions_dir / "a4_plugin.toml").unlink()

    with pytest.raises(ConfigurationError, match="exactly A1 through A6"):
        load_condition_registry(conditions_dir)


def test_stray_condition_wrapper_is_an_error(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    stray = (conditions_dir / "a1_baseline.toml").read_text(encoding="utf-8")
    (conditions_dir / "z9_stray.toml").write_text(
        stray.replace('condition_id = "A1"', 'condition_id = "Z9"'),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="exactly A1 through A6"):
        load_condition_registry(conditions_dir)


def test_duplicate_condition_id_is_an_error(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    duplicate = (conditions_dir / "a1_baseline.toml").read_text(encoding="utf-8")
    (conditions_dir / "a4_plugin.toml").write_text(duplicate, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Duplicate condition_id"):
        load_condition_registry(conditions_dir)


def test_frozen_prompt_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    prompt_file = conditions_dir / "prompts" / "a1_single_shot.md"
    prompt_file.write_text(
        prompt_file.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="hash mismatch"):
        load_condition_registry(conditions_dir)


def test_missing_frozen_prompt_file_fails_closed(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    (conditions_dir / "prompts" / "a1_single_shot.md").unlink()

    with pytest.raises(ConfigurationError, match="Missing frozen prompt"):
        load_condition_registry(conditions_dir)


def test_stage_hash_without_path_is_an_error(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    wrapper = conditions_dir / "a4_plugin.toml"
    wrapper.write_text(
        wrapper.read_text(encoding="utf-8").replace(
            'id = "plugin_session"',
            'id = "plugin_session"\nsha256 = "0" ',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="without a path"):
        load_condition_registry(conditions_dir)
