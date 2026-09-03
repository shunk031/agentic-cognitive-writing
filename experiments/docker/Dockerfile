# syntax=docker/dockerfile:1

ARG UV_VERSION=0.11.32

FROM ghcr.io/astral-sh/uv:${UV_VERSION}@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c AS uv

FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ARG TARGETARCH
ARG CODEX_VERSION=0.146.0
ARG CODEX_ARM64_SHA256=975bac91562abeedeb8f79636d51a86649b31f34a9de6a3bcb059565b6cf1f87
ARG CODEX_AMD64_SHA256=5ba3b9405543953081f661d0854d266f76e2abbe51d41349355a36de7673776a
ARG GIT_VERSION=1:2.39.5-0+deb12u3
ARG UV_VERSION=0.11.32

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/codex \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_NO_SYNC=1 \
    UV_PROJECT_ENVIRONMENT=/tmp/uv-project-env

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
        git="${GIT_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

RUN set -eux; \
    target_arch="${TARGETARCH:-}"; \
    if [ -z "${target_arch}" ]; then \
        case "$(dpkg --print-architecture)" in \
            arm64) target_arch=arm64 ;; \
            amd64) target_arch=amd64 ;; \
            *) echo "Unsupported base architecture" >&2; exit 1 ;; \
        esac; \
    fi; \
    case "${target_arch}" in \
        arm64) \
            codex_asset='codex-aarch64-unknown-linux-musl.tar.gz'; \
            codex_binary='codex-aarch64-unknown-linux-musl'; \
            codex_sha256="${CODEX_ARM64_SHA256}"; \
            ;; \
        amd64) \
            codex_asset='codex-x86_64-unknown-linux-musl.tar.gz'; \
            codex_binary='codex-x86_64-unknown-linux-musl'; \
            codex_sha256="${CODEX_AMD64_SHA256}"; \
            ;; \
        *) \
            echo "Unsupported Docker architecture: ${target_arch}" >&2; \
            exit 1; \
            ;; \
    esac; \
    curl --fail --location --retry 3 --retry-all-errors \
        "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/${codex_asset}" \
        --output /tmp/codex.tar.gz; \
    printf '%s  %s\n' "${codex_sha256}" /tmp/codex.tar.gz | sha256sum --check --status; \
    tar --extract --gzip --file /tmp/codex.tar.gz --directory /tmp; \
    install --mode 0755 "/tmp/${codex_binary}" /usr/local/bin/codex; \
    rm -f /tmp/codex.tar.gz "/tmp/${codex_binary}"; \
    codex --version | grep --fixed-strings "${CODEX_VERSION}"; \
    uv --version | grep --fixed-strings "uv ${UV_VERSION}"; \
    python --version | grep --fixed-strings 'Python 3.12.11'; \
    git --version | grep --fixed-strings '2.39.5'

RUN groupadd --gid 1000 codex \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/sh codex \
    && mkdir --parents /home/codex/.codex /workspace \
    && chown --recursive codex:codex /home/codex /workspace

COPY experiments/docker/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY experiments/docker/runner-shim.sh /tmp/runner-shim.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && python -m venv "${UV_PROJECT_ENVIRONMENT}" \
    && install --mode 0755 /tmp/runner-shim.sh \
        "${UV_PROJECT_ENVIRONMENT}/bin/agentic-cogwriter-runner"

USER codex
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uv", "run", "--package", "agentic-cogwriter", "agentic-cogwriter-runner", "--help"]
