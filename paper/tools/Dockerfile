FROM texlive/texlive:latest-small

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

RUN for attempt in 1 2 3; do \
        if tlmgr option repository https://mirror.ctan.org/systems/texlive/tlnet \
            && tlmgr update --self \
            && tlmgr install inconsolata dblfloatfix sttools epigraph nextpage helvetic fvextra; then \
            exit 0; \
        fi; \
        echo "tlmgr attempt ${attempt}/3 failed" >&2; \
        if [ "${attempt}" -lt 3 ]; then sleep 5; fi; \
    done; \
    echo "tlmgr failed after 3 attempts" >&2; \
    exit 1
