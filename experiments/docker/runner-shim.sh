#!/bin/sh

# @file experiments/docker/runner-shim.sh
# @brief Run the mounted experiment runner source tree.
# @description
#   The Docker image pre-creates the uv project environment because the
#   runner has no runtime dependencies. The source tree is mounted at
#   /workspace when experiments/docker/run.sh starts the container.

set -eu

export PYTHONPATH="/workspace/experiments/src${PYTHONPATH:+:${PYTHONPATH}}"
exec python -c \
    'from agentic_cogwriter.runner.cli import main; raise SystemExit(main())' "$@"
