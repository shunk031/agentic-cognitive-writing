#!/usr/bin/env bash

# @file experiments/docker/run.sh
# @brief Run the experiment runner inside the disposable Docker environment.
# @description
#   The script builds the pinned image on first use, mounts the repository
#   read-write at /workspace, and mounts the host Codex configuration read-only
#   at the container user's configuration path. Provider values come from an
#   optional runtime env file; common proxy variables pass through when set.
#   When both auth options are set, the script generates a temporary helper
#   stub and mounts it read-only at the requested command path.
# @option --env-file PATH Read provider values from a gitignored env file.
# @option --ca-file PATH Mount an optional CA certificate for proxy trust.
# @option --auth-command NAME Mount a generated runtime auth helper named NAME.
# @option --auth-env VAR Read the credential from environment variable VAR.
# @option --image IMAGE Use IMAGE instead of the local default image tag.
# @option --build Rebuild the local image before starting the container.
# @option --dry-run Print Docker arguments without starting a container.
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
auth_command=''
auth_env=''
force_build=false
dry_run=false
command_args=()
auth_stub_dir=''

# @description Remove the generated runtime auth helper after the wrapper exits.
function cleanup() {
    if [[ -n "${auth_stub_dir}" ]]; then
        rm -rf -- "${auth_stub_dir}"
    fi
}

trap cleanup EXIT

# @description Print the command-line options accepted by this wrapper.
function usage() {
    printf '%s\n' \
        'Usage: experiments/docker/run.sh [options] [-- runner-args...]' \
        '' \
        'Options:' \
        '  --env-file PATH  Read provider values from a gitignored env file.' \
        '  --ca-file PATH   Mount an optional CA certificate for proxy trust.' \
        '  --auth-command NAME  Mount a generated runtime auth helper named NAME.' \
        '  --auth-env VAR   Read the credential from environment variable VAR.' \
        '  --image IMAGE    Use IMAGE instead of the local default image tag.' \
        '  --build          Rebuild the local image before starting the container.' \
        '  --dry-run        Print Docker arguments without starting a container.' \
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
        --auth-command)
            (($# >= 2)) || die '--auth-command requires a name'
            auth_command="$2"
            shift 2
            ;;
        --auth-env)
            (($# >= 2)) || die '--auth-env requires a variable name'
            auth_env="$2"
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
        --dry-run)
            dry_run=true
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

if [[ -n "${auth_command}" || -n "${auth_env}" ]]; then
    [[ -n "${auth_command}" && -n "${auth_env}" ]] || die '--auth-command and --auth-env must be provided together'
    [[ "${auth_command}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die '--auth-command must be a command name without path separators'
    [[ "${auth_env}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die '--auth-env must be a shell variable name'

    auth_stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/agentic-cogwriter-auth.XXXXXX")"
    auth_stub_path="${auth_stub_dir}/${auth_command}"
    {
        printf '%s\n' '#!/bin/sh'
        printf "[ -n \"\${%s:-}\" ] || { printf \"%%s\\n\" \"credential variable is unset\" >&2; exit 1; }\n" "${auth_env}"
        printf "printf \"%%s\" \"\${%s}\"\n" "${auth_env}"
    } >"${auth_stub_path}"
    chmod 0755 "${auth_stub_path}"
fi

docker_args=(
    run
    --rm
    --init
    --security-opt seccomp=unconfined
    --user "$(id -u):$(id -g)"
    --workdir /workspace
    --mount "type=bind,src=${repo_root},dst=/workspace"
    --mount "type=bind,src=${host_codex_config},dst=/home/cog-writer-agent/.codex/config.toml,readonly"
    --env HOME=/home/cog-writer-agent
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

if [[ -n "${auth_stub_dir}" ]]; then
    docker_args+=(--mount "type=bind,src=${auth_stub_path},dst=/usr/local/bin/${auth_command},readonly")
fi

if ((${#command_args[@]} == 0)); then
    command_args=(--help)
fi

docker_command=("${docker_args[@]}" "${image}" uv run --package agentic-cogwriter agentic-cogwriter-runner "${command_args[@]}")

if [[ "${dry_run}" == true ]]; then
    printf 'docker'
    printf ' %q' "${docker_command[@]}"
    printf '\n'
    exit 0
fi

if [[ "${force_build}" == true ]] || ! docker image inspect "${image}" >/dev/null 2>&1; then
    docker build --tag "${image}" --file "${script_dir}/Dockerfile" "${repo_root}"
fi

docker "${docker_command[@]}"
