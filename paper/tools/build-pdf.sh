#!/usr/bin/env bash

# @file tools/build-pdf.sh
# @brief Build the ACL manuscript PDF in a container.
# @description
#   The first build creates a local TeX Live image from the official small
#   image and adds the manuscript's inconsolata and epigraph packages.
# @option --clean Remove generated files under build/ and exit.
# @example
#   ./tools/build-pdf.sh

set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
paper_dir=$(cd -- "$script_dir/.." && pwd)
build_dir="$paper_dir/build"
image_tag="agentic-cognitive-writing/texlive:latest-small-inconsolata-epigraph-nextpage"
pdf_path="$build_dir/acl_latex.pdf"
log_path="$build_dir/latexmk.log"

usage() {
    printf 'Usage: %s [--clean]\n' "${0##*/}"
}

case "${1-}" in
    "") ;;
    --clean)
        if (($# != 1)); then
            usage >&2
            exit 2
        fi
        rm -rf -- "$build_dir"
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

mkdir -p -- "$build_dir"
mkdir -p -- "$build_dir/.home"

if ! docker image inspect "$image_tag" >/dev/null 2>&1; then
    docker build \
        --build-arg "HTTP_PROXY=${HTTP_PROXY-}" \
        --build-arg "HTTPS_PROXY=${HTTPS_PROXY-}" \
        --build-arg "NO_PROXY=${NO_PROXY-}" \
        --file "$script_dir/Dockerfile" \
        --tag "$image_tag" \
        "$script_dir"
fi

set +e
docker run --rm \
    --user "$(id -u):$(id -g)" \
    --env "HTTP_PROXY=${HTTP_PROXY-}" \
    --env "HTTPS_PROXY=${HTTPS_PROXY-}" \
    --env "NO_PROXY=${NO_PROXY-}" \
    --env HOME=/workspace/build/.home \
    --volume "$paper_dir:/workspace" \
    --workdir /workspace \
    "$image_tag" \
    latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=/workspace/build acl_latex.tex \
    2>&1 | tee "$log_path"
build_status=${PIPESTATUS[0]}
set -e

page_count() {
    if command -v pdfinfo >/dev/null 2>&1; then
        pdfinfo "$1" | awk '$1 == "Pages:" {print $2; exit}'
        return
    fi
    python3 - "$1" "$build_dir/acl_latex.log" <<'PY'
import re
import sys

pdf_data = open(sys.argv[1], "rb").read()
counts = [int(value) for value in re.findall(rb"/Type\s*/Pages\b.*?/Count\s+(\d+)", pdf_data, re.S)]
if counts:
    print(max(counts))
    raise SystemExit

log_data = open(sys.argv[2], encoding="utf-8", errors="replace").read()
matches = re.findall(r"Output written on .* \((\d+) pages?,", log_data)
if not matches:
    raise SystemExit("could not determine PDF page count")
print(matches[-1])
PY
}

diagnostic_log="$build_dir/acl_latex.log"
if [[ ! -f "$diagnostic_log" ]]; then
    diagnostic_log="$log_path"
fi

overfull_count=$(grep -Ec '^Overfull \\hbox' "$diagnostic_log" || true)
underfull_count=$(grep -Ec '^Underfull \\hbox' "$diagnostic_log" || true)
undefined_reference_count=$(grep -Eic 'LaTeX Warning: Reference .* undefined on input line' "$diagnostic_log" || true)
undefined_citation_count=$(grep -Eic 'LaTeX Warning: Citation .* undefined on input line' "$diagnostic_log" || true)
undefined_macro_count=$(grep -Eic 'Undefined control sequence' "$diagnostic_log" || true)

printf '\nBuild summary\n'
if [[ -f "$pdf_path" ]]; then
    printf 'Pages: %s\n' "$(page_count "$pdf_path")"
else
    printf 'Pages: unavailable\n'
fi
printf 'Overfull hbox warnings: %s\n' "$overfull_count"
printf 'Underfull hbox warnings: %s\n' "$underfull_count"
printf 'Undefined references: %s\n' "$undefined_reference_count"
printf 'Undefined citations: %s\n' "$undefined_citation_count"
printf 'Undefined macros: %s\n' "$undefined_macro_count"
printf 'PDF: %s\n' "$pdf_path"

if ((overfull_count > 0)); then
    printf 'Overfull hbox locations:\n'
    grep -En '^Overfull \\hbox' "$diagnostic_log" || true
fi

exit "$build_status"
