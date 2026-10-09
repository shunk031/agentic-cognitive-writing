FROM texlive/texlive:latest-small

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

RUN set -eu; \
    for repository in \
        https://mirrors.mit.edu/CTAN/systems/texlive/tlnet \
        https://mirrors.ibiblio.org/pub/mirrors/CTAN/systems/texlive/tlnet \
        https://mirror.math.princeton.edu/pub/mirrors/CTAN/systems/texlive/tlnet; do \
        echo "Trying TeX Live repository: ${repository}" >&2; \
        if tlmgr option repository "${repository}" \
            && tlmgr update --self \
            && tlmgr install inconsolata dblfloatfix sttools epigraph nextpage helvetic fvextra tcolorbox pdfcol threeparttable; then \
            exit 0; \
        fi; \
        echo "TeX Live repository failed: ${repository}" >&2; \
    done; \
    echo "tlmgr failed for all pinned repositories" >&2; \
    exit 1
