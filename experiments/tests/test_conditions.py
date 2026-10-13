import shutil
from pathlib import Path

import pytest

from agentic_cogwriter.paths import EXPERIMENTS_ROOT, REPOSITORY_ROOT
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
        "17f8982911d5087d60e901087f7e78bb1652e3443d285f1a8ebdc6d5f6f09728"
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
    for condition_id in ("A4", "A5", "A6", "A7", "A8", "B1"):
        stages = registry[condition_id].stages
        assert [stage.stage_id for stage in stages] == ["plugin_session"]
        assert stages[0].path is None
        assert stages[0].sha256 is None


def test_a10_runs_fixed_self_refine_rounds_without_cogwriter_components() -> None:
    registry = load_condition_registry()
    a2, a10 = registry["A2"], registry["A10"]

    assert a10.skill_name == "writing-self-refine"
    for field in (
        "package_name",
        "goal_events",
        "event_types",
        "require_goal_events",
        "require_delegation",
        "product_requires_draft",
    ):
        assert getattr(a10, field) == getattr(a2, field), field

    rounds = (len(a10.stages) - 1) // 2
    assert rounds >= 1
    assert [stage.stage_id for stage in a10.stages] == [
        "draft",
        *(
            f"{step}_{n}"
            for n in range(1, rounds + 1)
            for step in ("feedback", "refine")
        ),
    ]
    assert a10.process_order == ("draft", *(("feedback", "refine") * rounds))
    assert a10.min_events == a10.max_events == len(a10.stages)
    readme = (CONDITIONS_DIR / "README.md").read_text(encoding="utf-8")
    assert f"A10 runs k = {rounds} Feedback and Refine rounds" in readme

    role_lines = {
        line.strip()
        for role in ("planning", "translating", "reviewing")
        for line in (REPOSITORY_ROOT / "plugin" / "skills" / role / "SKILL.md")
        .read_text(encoding="utf-8")
        .splitlines()
        if len(line.strip()) > 40
    }
    for stage in {stage.path for stage in a10.stages}:
        text = stage.read_text(encoding="utf-8")
        assert not any(line in text for line in role_lines), stage
        for excluded in ("Monitor", "goal", "trace", "delegat", "subagent"):
            assert excluded not in text, (stage, excluded)


def test_a9_keeps_the_a2_harness_and_adds_role_guidance() -> None:
    registry = load_condition_registry()
    a2, a9 = registry["A2"], registry["A9"]

    for field in (
        "skill_name",
        "package_name",
        "trace_processes",
        "goal_events",
        "event_types",
        "min_events",
        "max_events",
        "process_order",
        "require_goal_events",
        "require_delegation",
        "product_requires_draft",
    ):
        assert getattr(a9, field) == getattr(a2, field), field
    assert [stage.stage_id for stage in a9.stages] == [
        stage.stage_id for stage in a2.stages
    ]

    roles = ("planning", "translating", "reviewing")
    kept_role_sentences = {
        "planning": (
            "Separate known material, plausible ideas, and unsupported claims.",
            "The organizing work makes meaning rather than merely rearranging bullets.",
        ),
        "translating": (
            "do not let fluent wording override the rhetorical purpose.",
            "Do not invent sources, quotations, statistics, or facts.",
        ),
        "reviewing": (
            "Distinguish goal and evidence failures from organization and "
            "sentence failures.",
            "Do not invent citations or claims.",
        ),
    }
    for a2_stage, a9_stage, role in zip(a2.stages, a9.stages, roles, strict=True):
        a2_text = a2_stage.path.read_text(encoding="utf-8")
        a9_text = a9_stage.path.read_text(encoding="utf-8")
        assert a2_text.split("\n\n")[1] in a9_text
        role_text = (
            REPOSITORY_ROOT / "plugin" / "skills" / role / "SKILL.md"
        ).read_text(encoding="utf-8")
        for sentence in kept_role_sentences[role]:
            assert sentence in role_text
            assert sentence in a9_text
        for excluded in (
            "Monitor",
            "goal network",
            "goals.md",
            "trace",
            "delegat",
            "brief",
            "user",
            "fallback",
        ):
            assert excluded not in a9_text


def test_a11_keeps_the_a1_harness_with_only_a_neutral_instruction() -> None:
    registry = load_condition_registry()
    a1, a11 = registry["A1"], registry["A11"]

    for field in (
        "package_name",
        "trace_processes",
        "goal_events",
        "event_types",
        "min_events",
        "max_events",
        "process_order",
        "require_goal_events",
        "require_delegation",
        "product_requires_draft",
    ):
        assert getattr(a11, field) == getattr(a1, field), field
    assert [(stage.stage_id, stage.path) for stage in a11.stages] == [
        ("plugin_session", None)
    ]

    skill_text = (
        EXPERIMENTS_ROOT / "baselines/skills/writing-plain-agent/SKILL.md"
    ).read_text(encoding="utf-8")
    assert (
        "Write the requested document. Keep your working draft in a file in the "
        "workspace; you may plan, draft, and revise it as you see fit before "
        "returning the complete final document."
    ) in skill_text
    lowered = skill_text.lower()
    for excluded in (
        "monitor",
        "goal",
        "audience",
        "planning",
        "translating",
        "reviewing",
        "evaluate",
        "rhetorical",
        "delegat",
    ):
        assert excluded not in lowered


def test_a12_combines_the_a5_a6_and_a8_removals() -> None:
    registry = load_condition_registry()
    a4, a5, a8, a12 = (registry[c] for c in ("A4", "A5", "A8", "A12"))

    for field in ("trace_processes", "min_events", "max_events"):
        assert getattr(a12, field) == getattr(a4, field), field
    assert a12.event_types == a5.event_types == ("process_switch",)
    assert a12.package_name == a5.package_name
    assert (a12.goal_events, a12.require_goal_events) == ("forbidden", False)
    assert (a5.goal_events, a5.require_goal_events) == ("forbidden", False)
    assert a12.require_delegation is a8.require_delegation is False
    assert a12.process_order is None
    assert [stage.stage_id for stage in a12.stages] == ["plugin_session"]

    skills = REPOSITORY_ROOT / "experiments" / "plugin" / "skills"
    a12_text = (skills / a12.skill_name / "SKILL.md").read_text(encoding="utf-8")
    kept_sentences = {
        "cognitive-writing-no-goal-network": (
            "Do not create or modify `.writing/goals.md`, whether it exists or not.",
            "Never request goal-setting.",
        ),
        "cognitive-writing-fixed-order": (
            "Follow the fixed `Planning`, `Translating`, then `Reviewing` order",
        ),
        "cognitive-writing-single-context": (
            "Perform every selected process in your own context instead of "
            "delegating it.",
        ),
    }
    for source, sentences in kept_sentences.items():
        source_text = (skills / source / "SKILL.md").read_text(encoding="utf-8")
        for sentence in sentences:
            assert sentence in source_text, (source, sentence)
            assert sentence in a12_text, (source, sentence)
    for excluded in (
        "fork_context",
        "goal_id",
        "regeneration proposals",
        "goals-format.md",
    ):
        assert excluded not in a12_text, excluded


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
        "A7": "confirmatory",
        "A8": "exploratory",
        "A9": "exploratory",
        "A10": "exploratory",
        "A11": "exploratory",
        "A12": "exploratory",
        "B1": "exploratory",
        "B2": "exploratory",
    }


def test_registry_parses_delegation_requirement_with_false_default() -> None:
    registry = load_condition_registry()

    assert registry["A1"].require_delegation is False
    assert {
        condition_id
        for condition_id, condition in registry.items()
        if condition.require_delegation
    } == {"A3", "A4", "A5", "A6", "B1"}
    assert registry["A8"].require_delegation is False


def test_registry_rejects_non_boolean_delegation_requirement(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    wrapper_path = conditions_dir / "a4_plugin.toml"
    wrapper_path.write_text(
        wrapper_path.read_text(encoding="utf-8").replace(
            "require_delegation = true", 'require_delegation = "true"'
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigurationError,
        match="trace.require_delegation must be a boolean",
    ):
        load_condition_registry(conditions_dir)


def test_missing_condition_wrapper_is_an_error(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    (conditions_dir / "a4_plugin.toml").unlink()

    with pytest.raises(ConfigurationError, match="must define exactly"):
        load_condition_registry(conditions_dir)


def test_stray_condition_wrapper_is_an_error(tmp_path: Path) -> None:
    conditions_dir = _copy_conditions(tmp_path)
    stray = (conditions_dir / "a1_baseline.toml").read_text(encoding="utf-8")
    (conditions_dir / "z9_stray.toml").write_text(
        stray.replace('condition_id = "A1"', 'condition_id = "Z9"'),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="must define exactly"):
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
