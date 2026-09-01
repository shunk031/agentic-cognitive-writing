#!/usr/bin/env bash

# @file tools/validate-skills.sh
# @brief Run both pinned upstream skill validators against every bundled skill.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

curl --fail --silent --show-error --location --retry 1 \
  "https://raw.githubusercontent.com/anthropics/skills/3b3fad96af16a10759d930941b4520ba0c40edae/skills/skill-creator/scripts/quick_validate.py" \
  --output "$tmp_dir/anthropic-quick_validate.py"
curl --fail --silent --show-error --location --retry 1 \
  "https://raw.githubusercontent.com/openai/skills/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-creator/scripts/quick_validate.py" \
  --output "$tmp_dir/openai-quick_validate.py"

status=0
for skill_dir in "$repo_root"/plugin/skills/*/; do
  uv run --with pyyaml python "$tmp_dir/anthropic-quick_validate.py" "$skill_dir" || status=1
  uv run --with pyyaml python "$tmp_dir/openai-quick_validate.py" "$skill_dir" || status=1
done
exit "$status"
