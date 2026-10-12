from agentic_cogwriter.analysis.draft_writes import file_writes, summarize


def _change(path: str) -> dict:
    return {"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "/run/workspace/" + path}]}}


def test_counts_draft_rewrites_from_file_changes() -> None:
    events = [_change(".writing/draft.md"), _change(".writing/trace/process.jsonl"), _change(".writing/draft.md")]
    counts = file_writes(events, any_file=False)
    assert counts == {".writing/draft.md": 2}
    assert summarize([counts, file_writes(events[:1], any_file=False)]) == {"completed_runs": 2, "wrote_draft": 2, "rewrote_draft": 1}
