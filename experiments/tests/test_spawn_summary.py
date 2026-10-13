from agentic_cogwriter.analysis.spawn_summary import mean_spawns


def test_mean_spawns_counts_attempted_runs() -> None:
    assert mean_spawns({"B1": [9, 3, 0], "A4": []}) == {"B1": {"attempted_runs": 3, "mean_spawns": 4.0}}
