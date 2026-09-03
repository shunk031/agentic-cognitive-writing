# Primary benchmark prompt manifests

This directory contains the pinned benchmark prompt manifests for experimenters who regenerate or verify them.

## Reproduce

Run from the repository root:

```bash
uv run --package agentic-cogwriter agentic-cogwriter-materialize --benchmark all
uv run --package agentic-cogwriter agentic-cogwriter-recompute-dolomites-split
uv run pytest
```

The materializer downloads only pinned source files into `.cache/benchmarks/`,
verifies each source hash before parsing it, and does not check raw upstream
files into git. Existing manifests and provenance records are immutable:
regeneration succeeds only when the bytes are identical.

## Data layout

The three checked-in JSONL files are the only prompt inputs permitted by the
experiment protocol. The materialization code belongs to the
`agentic-cogwriter` uv workspace member under `experiments/src`; this directory
contains data files only:

```text
experiments/
├── src/agentic_cogwriter/       # materialization code
├── tests/                       # member tests
└── prompts/                     # benchmark data (not Python source)
    ├── manifests/               # immutable prompt manifests
    ├── provenance.json          # pins, hashes, licenses, and counts
    └── dolomites_split.json     # archive-derived split evidence
```

## Manifest schema

Each manifest row contains:

`prompt_id`, `benchmark_name`, `source_version`, `prompt_text`,
`requested_output_constraints`, and `hash`.

`hash` is SHA-256 over the canonical UTF-8 JSON object containing every field
except `hash` itself. Canonical JSON uses sorted keys, no insignificant
whitespace, and `ensure_ascii=false`.

## Pinned sources and counts

| Benchmark | Pinned source | Source content | Manifest |
| --- | --- | ---: | ---: |
| WritingBench | [`X-PLUG/WritingBench@9c24bb67`](https://github.com/X-PLUG/WritingBench/tree/9c24bb67fd7451a2eacf5810aa7721e3a8b3bdad) | `benchmark_query/benchmark_all.jsonl`, SHA-256 `026e3f9482ff3474c802cd43f5cae9fd584e10d0848d3e0a152695434becbc98` | 1,000 |
| HelloBench | [`Quehry/HelloBench@92c7d469`](https://github.com/Quehry/HelloBench/tree/92c7d469230b5b6b6ee1bfc1ea2ce49cb9125b57) | Five `data/main_data/*.jsonl` files, hashes recorded in [`provenance.json`](provenance.json) | 647 |
| DoLoMiTes | [`google-deepmind/dolomites@8331dd99`](https://github.com/google-deepmind/dolomites/tree/8331dd998bf510cacc58d10ad613c9e685787747) plus the released [`dolomites_examples.zip`](https://dolomites-benchmark.s3.us-west-2.amazonaws.com/dolomites_examples.zip) | Archive SHA-256 `62ee47b4cdf67d1efd7a21029384a929e3d66cab49989aab85ea3534b8b86c32` | 820 dev rows |

WritingBench uses the query text from its curated 1,000-query file. HelloBench
uses the `instruction` and separate `requirements` fields from its five main
testing files. DoLoMiTes combines the task objective, procedure, input
specification, and supplied example input; its output requirements and notes
become constraints. Reference outputs are intentionally omitted.

### DoLoMiTes split gate

[`recompute_dolomites_split.py`](../src/agentic_cogwriter/prompts/recompute_dolomites_split.py) counts JSONL records in the two named archive
members and writes [`dolomites_split.json`](dolomites_split.json). The observed
archive split is **820 dev / 1,037 test**. This is the authoritative result;
the upstream README's 830-dev statement is not used. Only the 820-row dev
subset is in the manifest, and the test subset is never used for primary
analysis.

## License and attribution

WritingBench prompt material is Apache-2.0. HelloBench prompt material is MIT.
DoLoMiTes materials are CC BY 4.0. Redistributing DoLoMiTes-derived material
requires attribution to DeepMind Technologies Limited and the following note:
development examples became prompt rows, and reference outputs were omitted.
The machine-readable license and provenance record is in
[`provenance.json`](provenance.json).
