#!/usr/bin/env bash

# @file tools/build-markdown.sh
# @brief Render the manuscript as Markdown and verify it against the PDF.
# @description
#   Rebuilds PDF metadata, expands manuscript inputs, and runs pinned Pandoc
#   in Docker. Writes Markdown and its verification report under build/.
# @example
#   ./tools/build-markdown.sh

set -Eeuo pipefail

if (($#)); then
    printf 'Usage: %s\n' "${0##*/}" >&2
    exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
paper_dir=$(cd -- "$script_dir/.." && pwd)

uv run --no-project "$script_dir/check-reader-guards.py"
uv run --no-project "$script_dir/check-table-style.py"
"$script_dir/build-pdf.sh"
uv run --no-project "$script_dir/prepare-markdown-prompt-cards.py"
docker run --rm \
    --user "$(id -u):$(id -g)" \
    --volume "$paper_dir:/workspace" \
    --workdir /workspace \
    pandoc/core:3.6.4 \
    build/markdown-source.tex --from=latex --to=gfm-tex_math_dollars --wrap=none \
    --shift-heading-level-by=1 --output=build/acl_latex.md
uv run --no-project "$script_dir/check-markdown.py"
