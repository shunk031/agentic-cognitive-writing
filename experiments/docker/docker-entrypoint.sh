#!/bin/sh

# @file experiments/docker/docker-entrypoint.sh
# @brief Start a command with an optional mounted CA certificate.
# @description
#   The run script mounts a user-provided CA certificate at /run/user-ca.pem
#   only when the caller requests optional proxy trust wiring. The entrypoint
#   appends that certificate to the image trust bundle for the child command.

set -eu

if [ -e /run/user-ca.pem ]; then
    ca_bundle=/tmp/ca-bundle.pem
    cat /etc/ssl/certs/ca-certificates.crt /run/user-ca.pem >"${ca_bundle}"
    export SSL_CERT_FILE="${ca_bundle}"
    export CURL_CA_BUNDLE="${ca_bundle}"
fi

exec "$@"
