#!/usr/bin/env bash
set -euo pipefail

# Test-only placeholders; never load a local or production environment file.
export IMAGE_TAG=0000000000000000000000000000000000000000
export POSTGRES_DB=true_roi_ci POSTGRES_USER=true_roi_ci
export POSTGRES_PASSWORD=ci-only-placeholder
export CATALOG_SOURCE_URL=https://example.invalid/skins.json
export CATALOG_GROUPED_SOURCE_URL=https://example.invalid/skins-grouped.json
export CATALOG_EXTRA_SOURCE_BASE_URL=https://example.invalid
export SURFSHARK_WIREGUARD_PRIVATE_KEY=ci-only-placeholder
export SURFSHARK_WIREGUARD_ADDRESSES=10.0.0.2/32

docker compose --env-file /dev/null -f docker-compose.prod.yml config --quiet
