# Process-sequence analysis across three generation runs

[`process-sequences.json`](process-sequences.json) is the output of `agentic-cogwriter-process-sequences` from this branch's [`process_sequences.py`](../../../experiments/src/agentic_cogwriter/analysis/process_sequences.py), run over generation runs 1, 2, and 3 (one `--runs-root` each). Run roots are replaced by the labels `run-1`, `run-2`, and `run-3`, and the repository root by `.`; no other field is changed.

It supersedes the 2026-09-28 analysis behind the current trace macros. Because exact-cycle classification now applies the same leading-Planning reconstruction as cycle compliance, the exact single-cycle rate rises from 56.4% to 58.1% for Agentic CogWriter and from 50.8% to 56.1% for Fixed-order, and the trace-outcome split and its Fisher tests change accordingly; cycle-compliance rates are unchanged.
