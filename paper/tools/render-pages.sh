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
prebuilt_image="ghcr.io/shunk031/agentic-cognitive-writing/texlive:small-inconsolata-epigraph-nextpage"
render_stamp=$(date +%Y%m%d-%H%M%S)
render_dir="$paper_dir/build/render/$render_stamp"

if [[ ! -f "$pdf_path" ]]; then
    printf 'Missing PDF: %s\n' "$pdf_path" >&2
    exit 1
fi

# @description Use the local TeX image, pulling the prebuilt GHCR image first and building it if needed.
ensure_image() {
    if docker image inspect "$image_tag" >/dev/null 2>&1; then
        return 0
    fi

    printf 'Local TeX image is absent; trying prebuilt image %s.\n' "$prebuilt_image"
    if docker pull "$prebuilt_image" && docker tag "$prebuilt_image" "$image_tag"; then
        printf 'Tagged prebuilt TeX image as %s.\n' "$image_tag"
        return 0
    fi

    printf 'Could not pull the prebuilt TeX image; falling back to a local Docker build.\n' >&2
    docker build \
        --build-arg "HTTP_PROXY=${HTTP_PROXY-}" \
        --build-arg "HTTPS_PROXY=${HTTPS_PROXY-}" \
        --build-arg "NO_PROXY=${NO_PROXY-}" \
        --file "$script_dir/Dockerfile" \
        --tag "$image_tag" \
        "$script_dir"
}

mkdir -p -- "$render_dir"
ensure_image

for page_number in "$@"; do
    if [[ ! "$page_number" =~ ^[1-9][0-9]*$ ]]; then
        printf 'Invalid page number: %s\n' "$page_number" >&2
        exit 2
    fi
done

# One container renders every requested page, one Ghostscript process per CPU.
printf '%s\n' "$@" | docker run --rm -i \
    --user "$(id -u):$(id -g)" \
    --volume "$paper_dir:/workspace" \
    --workdir /workspace \
    "$image_tag" \
    xargs -P "$(nproc)" -I '{}' \
    gs -q -dSAFER -dBATCH -dNOPAUSE -sDEVICE=png16m -r110 \
    -dFirstPage='{}' -dLastPage='{}' \
    -sOutputFile="/workspace/build/render/$render_stamp/page-{}.png" \
    /workspace/build/acl_latex.pdf

printf 'Rendered pages under %s\n' "$render_dir"
