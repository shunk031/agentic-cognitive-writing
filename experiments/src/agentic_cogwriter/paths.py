"""Repository-relative paths shared by the experiment package."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPOSITORY_ROOT / "experiments"
PROMPT_DATA_ROOT = EXPERIMENTS_ROOT / "prompts"
MANIFESTS_DIR = PROMPT_DATA_ROOT / "manifests"
PROVENANCE_PATH = PROMPT_DATA_ROOT / "provenance.json"
DOLOMITES_SPLIT_PATH = PROMPT_DATA_ROOT / "dolomites_split.json"
BENCHMARK_CACHE_DIR = REPOSITORY_ROOT / ".cache" / "benchmarks"
