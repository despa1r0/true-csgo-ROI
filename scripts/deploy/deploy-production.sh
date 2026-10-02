#!/usr/bin/env bash

set -Eeuo pipefail

readonly APP_DIRECTORY="/opt/true-roi"
readonly COMPOSE_FILENAME="docker-compose.prod.yml"
readonly DEPLOY_SCRIPT_FILENAME="deploy-production.sh"

declare -a compose=()

usage() {
    echo "Usage: ${0##*/} <40-character-image-tag>" >&2
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

cleanup() {
    rm -f -- "$1" "$2"
    rmdir -- "$3" 2>/dev/null || true
}

wait_for_healthy() {
    local container_name="$1"
    local compose_service="$2"
    local log_lines="$3"
    local state="unknown"

    for ((attempt = 1; attempt <= 24; attempt++)); do
        state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_name}" 2>/dev/null || true)
        if [[ "${state}" == "healthy" || "${state}" == "unhealthy" || "${state}" == "exited" ]]; then
            break
        fi
        sleep 5
    done

    if [[ "${state}" != "healthy" ]]; then
        echo "${container_name} did not become healthy (state: ${state})" >&2
        "${compose[@]}" logs --tail="${log_lines}" "${compose_service}" >&2
        return 1
    fi
}

main() {
    [[ $# -eq 1 ]] || { usage; exit 2; }

    local image_tag="$1"
    [[ "${image_tag}" =~ ^[0-9a-f]{40}$ ]] || die "Invalid image tag: expected a commit SHA"
    [[ -d "${APP_DIRECTORY}" ]] || die "Application directory is missing: ${APP_DIRECTORY}"

    require_command docker
    require_command flock
    require_command mktemp
    require_command sed
    docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is required"

    cd "${APP_DIRECTORY}"

    local staged_compose="${COMPOSE_FILENAME}.${image_tag}.staged"
    local staged_script="${DEPLOY_SCRIPT_FILENAME}.${image_tag}.staged"
    [[ -f "${staged_compose}" ]] || die "Staged production Compose file is missing"
    [[ -f "${staged_script}" ]] || die "Staged deployment script is missing"

    exec 9>.deploy.lock
    flock -w 300 9 || die "Another deployment still holds ${APP_DIRECTORY}/.deploy.lock"

    local anonymous_docker_config
    anonymous_docker_config=$(mktemp -d)
    # Capture paths now: main's local variables are gone on a successful EXIT.
    local cleanup_command
    printf -v cleanup_command 'cleanup %q %q %q' \
        "${staged_compose}" "${staged_script}" "${anonymous_docker_config}"
    trap "${cleanup_command}" EXIT

    export DOCKER_CONFIG="${anonymous_docker_config}"
    export IMAGE_TAG="${image_tag}"

    docker compose --ansi never -f "${staged_compose}" config --quiet
    compose=(docker compose --ansi never -f "${staged_compose}")

    echo "Pulling production application images for ${image_tag}"
    "${compose[@]}" pull --quiet api csmoney-worker

    mv -f -- "${staged_compose}" "${COMPOSE_FILENAME}"
    compose=(docker compose --ansi never -f "${COMPOSE_FILENAME}")

    echo "Starting PostgreSQL"
    "${compose[@]}" up -d db
    wait_for_healthy true-roi-postgres db 50

    # POSTGRES_PASSWORD initializes only an empty volume. Keep an existing role
    # synchronized when the password in the VPS .env is intentionally rotated.
    local db_environment postgres_user postgres_db postgres_password
    db_environment=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' true-roi-postgres)
    postgres_user=$(sed -n 's/^POSTGRES_USER=//p' <<<"${db_environment}")
    postgres_db=$(sed -n 's/^POSTGRES_DB=//p' <<<"${db_environment}")
    postgres_password=$(sed -n 's/^POSTGRES_PASSWORD=//p' <<<"${db_environment}")
    unset db_environment
    if [[ -z "${postgres_user}" || -z "${postgres_db}" || -z "${postgres_password}" ]]; then
        die "PostgreSQL container is missing required environment values"
    fi

    echo "Synchronizing PostgreSQL role credentials"
    docker exec -i \
        -e TARGET_ROLE="${postgres_user}" \
        -e TARGET_DB="${postgres_db}" \
        -e TARGET_PASSWORD="${postgres_password}" \
        true-roi-postgres \
        sh -ec 'psql --username "$TARGET_ROLE" --dbname "$TARGET_DB" --set=ON_ERROR_STOP=1 --set=role_name="$TARGET_ROLE" --set=role_password="$TARGET_PASSWORD"' <<'SQL'
SELECT format('ALTER ROLE %I WITH PASSWORD %L', :'role_name', :'role_password') \gexec
SQL
    unset postgres_password

    echo "Seeding catalogue before replacing application containers"
    if ! "${compose[@]}" up --no-deps --abort-on-container-exit --exit-code-from catalog-seed catalog-seed; then
        echo "Catalogue seed failed" >&2
        "${compose[@]}" logs --tail=100 catalog-seed >&2
        exit 1
    fi

    # These containers share Gluetun's network namespace and must be removed
    # before the gateway can be recreated after a configuration change.
    "${compose[@]}" rm -sf api csmoney-worker

    echo "Starting Surfshark VPN gateway"
    "${compose[@]}" up -d --no-deps gluetun
    wait_for_healthy true-roi-gluetun gluetun 100

    echo "Starting production application services"
    "${compose[@]}" up -d --no-deps api csmoney-worker csmoney-demand
    wait_for_healthy true-roi-api api 30

    "${compose[@]}" ps --all
    local container state
    for container in true-roi-csmoney-crawler true-roi-csmoney-demand; do
        state=$(docker inspect --format '{{.State.Status}}' "${container}" 2>/dev/null || true)
        [[ "${state}" == "running" ]] || die "${container} is not running (state: ${state})"
    done

    mv -f -- "${staged_script}" "${DEPLOY_SCRIPT_FILENAME}"
    echo "Deployment healthy: ${image_tag}"
}

main "$@"
