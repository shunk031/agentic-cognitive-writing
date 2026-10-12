from agentic_cogwriter.analysis.length_control import PairObservation
from agentic_cogwriter.analysis.length_rule_agreement import agreement


def _pair(left_length: int, right_length: int, verdict: str) -> PairObservation:
    return PairObservation("WritingBench", "p", "j", "A4", "A1", left_length, right_length, verdict)


def test_agreement_counts_decided_pairs_with_unequal_lengths() -> None:
    rows = [_pair(200, 100, "left"), _pair(200, 100, "right"), _pair(100, 100, "left"), _pair(200, 100, "tie")]
    result = agreement(rows)["WritingBench"]
    assert (result["agreeing"], result["decided_pairs"]) == (1, 2)
