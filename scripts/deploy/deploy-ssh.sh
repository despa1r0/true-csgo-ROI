#!/usr/bin/env bash
set -euo pipefail

validate() {
    local variable
    for variable in VPS_SSH_KEY VPS_HOST VPS_USER VPS_PORT; do
        if [[ -z "${!variable:-}" ]]; then
            echo "Missing required repository secret: ${variable}" >&2
            return 1
        fi
    done
    if [[ ! "${IMAGE_TAG:-}" =~ ^[0-9a-f]{40}$ ]]; then
        echo 'Invalid image tag: expected a commit SHA' >&2
        return 1
    fi
    if [[ ! "${VPS_PORT}" =~ ^[0-9]+$ ]] || (( VPS_PORT < 1 || VPS_PORT > 65535 )); then
        echo 'Invalid VPS_PORT: expected a port from 1 to 65535' >&2
        return 1
    fi
}

configure() {
    validate
    umask 077
    install -d -m 700 "${SSH_DIRECTORY}"
    printf '%s\n' "${VPS_SSH_KEY}" > "${SSH_DIRECTORY}/id_ed25519"
    chmod 600 "${SSH_DIRECTORY}/id_ed25519"
    if ! ssh-keyscan -H -T 10 -p "${VPS_PORT}" "${VPS_HOST}" > "${SSH_DIRECTORY}/known_hosts"; then
        echo 'Failed to retrieve the VPS SSH host key' >&2
        return 1
    fi
    chmod 600 "${SSH_DIRECTORY}/known_hosts"
    local known_host="${VPS_HOST}"
    if [[ "${VPS_PORT}" != 22 ]]; then
        known_host="[${VPS_HOST}]:${VPS_PORT}"
    fi
    if ! ssh-keygen -F "${known_host}" -f "${SSH_DIRECTORY}/known_hosts" >/dev/null; then
        echo 'No SSH host key found for VPS_HOST and VPS_PORT' >&2
        return 1
    fi
}

copy_files() {
    local file
    for file in docker-compose.prod.yml scripts/deploy/deploy-production.sh; do
        scp -i "${SSH_DIRECTORY}/id_ed25519" \
            -o UserKnownHostsFile="${SSH_DIRECTORY}/known_hosts" \
            -o StrictHostKeyChecking=yes \
            -o BatchMode=yes \
            -P "${VPS_PORT}" "${file}" \
            "${VPS_USER}@${VPS_HOST}:/opt/true-roi/${file##*/}.${IMAGE_TAG}.staged"
    done
}

deploy() {
    ssh -i "${SSH_DIRECTORY}/id_ed25519" \
        -o UserKnownHostsFile="${SSH_DIRECTORY}/known_hosts" \
        -o StrictHostKeyChecking=yes \
        -o BatchMode=yes \
        -p "${VPS_PORT}" "${VPS_USER}@${VPS_HOST}" \
        "bash '/opt/true-roi/deploy-production.sh.${IMAGE_TAG}.staged' '${IMAGE_TAG}'"
}

cleanup() {
    if [[ -d "${SSH_DIRECTORY}" ]]; then
        rm -f -- "${SSH_DIRECTORY}/id_ed25519" "${SSH_DIRECTORY}/known_hosts"
        rmdir -- "${SSH_DIRECTORY}"
    fi
}

case "${1:-}" in
    validate) validate ;;
    configure) configure ;;
    copy) copy_files ;;
    deploy) deploy ;;
    cleanup) cleanup ;;
    *) echo "Usage: ${0##*/} {validate|configure|copy|deploy|cleanup}" >&2; exit 2 ;;
esac
