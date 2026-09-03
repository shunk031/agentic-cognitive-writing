#!/usr/bin/env bash

# @file experiments/docker/run.sh
# @brief Run the experiment runner inside the disposable Docker environment.
# @description
#   The script builds the pinned image on first use, mounts the repository
#   read-write at /workspace, and mounts the host Codex configuration read-only
#   at the container user's configuration path. Provider values come from an
#   optional runtime env file; common proxy variables pass through when set.
# @option --env-file PATH Read provider values from a gitignored env file.
# @option --ca-file PATH Mount an optional CA certificate for proxy trust.
# @option --image IMAGE Use IMAGE instead of the local default image tag.
# @option --build Rebuild the local image before starting the container.
# @option -h | --help Print this usage text.
# @arg command_args Runner arguments after --.
# @example
#   experiments/docker/run.sh --env-file experiments/docker/provider.env -- --help

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "${script_dir}/../.." && pwd -P)"
image='agentic-cognitive-writing-experiment:local'
env_file=''
ca_file=''
force_build=false
command_args=()

# @description Print the command-line options accepted by this wrapper.
function usage() {
    printf '%s\n' \
        'Usage: experiments/docker/run.sh [options] [-- runner-args...]' \
        '' \
        'Options:' \
        '  --env-file PATH  Read provider values from a gitignored env file.' \
        '  --ca-file PATH   Mount an optional CA certificate for proxy trust.' \
        '  --image IMAGE    Use IMAGE instead of the local default image tag.' \
        '  --build          Rebuild the local image before starting the container.' \
        '  -h, --help       Print this usage text.'
}

# @description Print an error and stop the wrapper.
# @arg $1 message Error text for the caller.
function die() {
    printf 'error: %s\n' "$1" >&2
    exit 64
}

# @description Resolve a path supplied relative to the caller's current directory.
# @arg $1 path Path supplied on the command line.
function absolute_path() {
    local path="$1"
    if [[ "${path}" == /* ]]; then
        printf '%s\n' "${path}"
    else
        printf '%s/%s\n' "${PWD}" "${path}"
    fi
}

# @description Add a standard proxy variable when the caller exported it.
# @arg $1 name Environment-variable name to pass to Docker.
function append_proxy_env() {
    local name="$1"
    if [[ ${!name+x} == x ]]; then
        docker_args+=(--env "${name}")
    fi
}

while (($# > 0)); do
    case "$1" in
        --env-file)
            (($# >= 2)) || die '--env-file requires a path'
            env_file="$(absolute_path "$2")"
            shift 2
            ;;
        --ca-file)
            (($# >= 2)) || die '--ca-file requires a path'
            ca_file="$(absolute_path "$2")"
            shift 2
            ;;
        --image)
            (($# >= 2)) || die '--image requires a tag'
            image="$2"
            shift 2
            ;;
        --build)
            force_build=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            command_args=("$@")
            break
            ;;
        *)
            command_args=("$@")
            break
            ;;
    esac
done

[[ -n "${HOME:-}" ]] || die 'HOME must identify the host home directory'
host_codex_config="${HOME}/.codex/config.toml"
[[ -r "${host_codex_config}" ]] || die "missing readable ${host_codex_config}"

if [[ -n "${env_file}" ]]; then
    [[ -r "${env_file}" ]] || die "missing readable env file ${env_file}"
fi

if [[ -n "${ca_file}" ]]; then
    [[ -r "${ca_file}" ]] || die "missing readable CA file ${ca_file}"
fi

if [[ "${force_build}" == true ]] || ! docker image inspect "${image}" >/dev/null 2>&1; then
    docker build --tag "${image}" --file "${script_dir}/Dockerfile" "${repo_root}"
fi

docker_args=(
    run
    --rm
    --init
    --user "$(id -u):$(id -g)"
    --workdir /workspace
    --mount "type=bind,src=${repo_root},dst=/workspace"
    --mount "type=bind,src=${host_codex_config},dst=/home/codex/.codex/config.toml,readonly"
    --env HOME=/home/codex
)

if [[ -n "${env_file}" ]]; then
    docker_args+=(--env-file "${env_file}")
fi

for proxy_name in HTTP_PROXY HTTPS_PROXY NO_PROXY ALL_PROXY http_proxy https_proxy no_proxy all_proxy; do
    append_proxy_env "${proxy_name}"
done

if [[ -n "${ca_file}" ]]; then
    docker_args+=(--mount "type=bind,src=${ca_file},dst=/run/user-ca.pem,readonly")
fi

if ((${#command_args[@]} == 0)); then
    command_args=(--help)
fi

exec docker "${docker_args[@]}" "${image}" \
    uv run --package agentic-cogwriter agentic-cogwriter-runner "${command_args[@]}"
