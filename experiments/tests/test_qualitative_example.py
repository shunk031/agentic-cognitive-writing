from agentic_cogwriter.analysis.qualitative_example import excerpt, select


def test_excerpt_keeps_lines_and_truncates() -> None:
    assert excerpt("# Title\n\nOne two three", 3) == "# Title\nOne ..."


def test_select_is_seeded() -> None:
    pool = [{"prompt": str(i)} for i in range(50)]
    assert select(pool) == select(pool)
