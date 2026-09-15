import json
from pathlib import Path

from agentic_cogwriter.paths import MANIFESTS_DIR, PROMPT_DATA_ROOT
from agentic_cogwriter.prompts.prompt_sets import write_prompt_sets

PROMPT_SET_PATH = PROMPT_DATA_ROOT / "prompt_sets.json"

EXPECTED_BENCHMARKS = {
    "hellobench": {
        "pilot": [
            "hellobench-chat_072",
            "hellobench-chat_093",
            "hellobench-heuristic_text_generation_016",
            "hellobench-heuristic_text_generation_045",
            "hellobench-open_ended_qa_048",
            "hellobench-open_ended_qa_161",
            "hellobench-summarization_044",
            "hellobench-summarization_059",
            "hellobench-text_completion_001",
            "hellobench-text_completion_032",
        ],
        "hard": [
            "hellobench-summarization_012",
            "hellobench-summarization_062",
            "hellobench-summarization_024",
            "hellobench-summarization_065",
            "hellobench-summarization_031",
            "hellobench-summarization_017",
            "hellobench-text_completion_056",
            "hellobench-summarization_054",
            "hellobench-summarization_007",
            "hellobench-chat_017",
            "hellobench-chat_021",
            "hellobench-summarization_069",
            "hellobench-chat_003",
            "hellobench-summarization_063",
            "hellobench-text_completion_057",
            "hellobench-summarization_087",
            "hellobench-text_completion_038",
            "hellobench-summarization_077",
            "hellobench-summarization_095",
            "hellobench-summarization_057",
        ],
    },
    "writingbench": {
        "pilot": [
            "writingbench-0129",
            "writingbench-0195",
            "writingbench-0196",
            "writingbench-0250",
            "writingbench-0257",
            "writingbench-0360",
            "writingbench-0361",
            "writingbench-0479",
            "writingbench-0641",
            "writingbench-0868",
        ],
        "hard": [
            "writingbench-0037",
            "writingbench-0532",
            "writingbench-0984",
            "writingbench-0774",
            "writingbench-0561",
            "writingbench-0003",
            "writingbench-0925",
            "writingbench-0945",
            "writingbench-0322",
            "writingbench-0502",
            "writingbench-0905",
            "writingbench-0104",
            "writingbench-0520",
            "writingbench-0184",
            "writingbench-0068",
            "writingbench-0516",
            "writingbench-0490",
            "writingbench-0963",
            "writingbench-0739",
            "writingbench-0579",
        ],
    },
    "dolomites": {
        "pilot": [
            "dolomites-1029",
            "dolomites-1226",
            "dolomites-1341",
            "dolomites-1377",
            "dolomites-1419",
            "dolomites-1850",
            "dolomites-224",
            "dolomites-32",
            "dolomites-364",
            "dolomites-554",
        ],
        "hard": [
            "dolomites-1358",
            "dolomites-1359",
            "dolomites-1360",
            "dolomites-319",
            "dolomites-1494",
            "dolomites-210",
            "dolomites-524",
            "dolomites-1761",
            "dolomites-1495",
            "dolomites-1497",
            "dolomites-1499",
            "dolomites-131",
            "dolomites-133",
            "dolomites-451",
            "dolomites-790",
            "dolomites-1781",
            "dolomites-1493",
            "dolomites-820",
            "dolomites-423",
            "dolomites-1496",
        ],
    },
}


def test_checked_in_prompt_sets_match_the_recorded_selection() -> None:
    artifact = json.loads(PROMPT_SET_PATH.read_text(encoding="utf-8"))

    assert artifact["benchmarks"] == EXPECTED_BENCHMARKS
    for benchmark in EXPECTED_BENCHMARKS:
        assert set(artifact["benchmarks"][benchmark]["pilot"]).isdisjoint(
            artifact["benchmarks"][benchmark]["hard"]
        )


def test_prompt_sets_regenerate_byte_for_byte_from_committed_manifests(
    tmp_path: Path,
) -> None:
    generated = tmp_path / "prompt_sets.json"

    write_prompt_sets(generated, MANIFESTS_DIR)

    assert generated.read_bytes() == PROMPT_SET_PATH.read_bytes()
