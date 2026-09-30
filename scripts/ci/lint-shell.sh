#!/usr/bin/env bash
set -euo pipefail

mapfile -d '' -t scripts < <(find scripts -type f -name '*.sh' -print0 | sort -z)
for script in "${scripts[@]}"; do
    bash -n "${script}"
done
shellcheck "${scripts[@]}"
