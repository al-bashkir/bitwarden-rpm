#!/usr/bin/env bash
set -euo pipefail

main() {
    local -r bitwarden_dir="/usr/lib/bitwarden"
    local -r launcher_path="${bitwarden_dir}/bitwarden"
    local -a flags=()

    if [[ ! -x "${launcher_path}" ]]; then
        printf 'Error: %s is not executable\n' "${launcher_path}" >&2
        exit 1
    fi

    if [[ -n "${BITWARDEN_FLAGS:-}" ]]; then
        # shellcheck disable=SC2206
        flags+=(${BITWARDEN_FLAGS})
    fi

    exec "${launcher_path}" "${flags[@]}" "$@"
}

main "$@"
