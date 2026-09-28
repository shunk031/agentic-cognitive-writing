#!/usr/bin/env bash

# @file tools/render-pages.sh
# @brief Render selected manuscript pages to PNG inside the manuscript's TeX image.
# @description
#   Takes one or more positive page numbers, never removes prior renders, and
#   writes one 110 dpi PNG per page under a timestamped build/render directory.
# @arg page_number One or more positive PDF page numbers to render.
# @example
#   ./tools/render-pages.sh 1 7 9

set -Eeuo pipefail

if (($# == 0)); then
    printf 'Usage: %s PAGE [PAGE ...]\n' "${0##*/}" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
paper_dir=$(cd -- "$script_dir/.." && pwd)
pdf_path="$paper_dir/build/acl_latex.pdf"
image_tag="agentic-cognitive-writing/texlive:latest-small-inconsolata-epigraph-nextpage"
render_stamp=$(date +%Y%m%d-%H%M%S)
render_dir="$paper_dir/build/render/$render_stamp"

if [[ ! -f "$pdf_path" ]]; then
    printf 'Missing PDF: %s\n' "$pdf_path" >&2
    exit 1
fi

mkdir -p -- "$render_dir"

for page_number in "$@"; do
    if [[ ! "$page_number" =~ ^[1-9][0-9]*$ ]]; then
        printf 'Invalid page number: %s\n' "$page_number" >&2
        exit 2
    fi
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        --volume "$paper_dir:/workspace" \
        --workdir /workspace \
        "$image_tag" \
        gs -dSAFER -dBATCH -dNOPAUSE -sDEVICE=png16m -r110 \
        -dFirstPage="$page_number" -dLastPage="$page_number" \
        -sOutputFile="/workspace/build/render/$render_stamp/page-$page_number.png" \
        /workspace/build/acl_latex.pdf
done

printf 'Rendered pages under %s\n' "$render_dir"
