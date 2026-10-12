from agentic_cogwriter.analysis.language_drift import drift, mainly_chinese


def test_mainly_chinese_compares_han_and_latin() -> None:
    assert mainly_chinese("中文文本 ab")
    assert not mainly_chinese("English text 中")


def test_drift_counts_english_prompts_answered_in_chinese() -> None:
    prompts = {"p1": "Write a report.", "p2": "写一份报告。", "p3": "Write a memo."}
    outputs = {
        "A1": {"p1": "这是报告。", "p2": "报告", "p3": "A memo."},
        "A4": {"p1": "这是报告。", "p3": "这是备忘录。"},
    }
    result = drift(outputs, prompts)
    assert result["by_condition"]["A1"] == {"english_completed": 2, "drifted": 1}
    assert result["by_condition"]["A4"] == {"english_completed": 2, "drifted": 2}
    assert result["drifted_in_every_condition"] == ["p1"]
    assert result["every_condition_with_han_in_prompt"] == []
