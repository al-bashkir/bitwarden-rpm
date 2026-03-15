#!/usr/bin/bash
# Bitwarden Desktop launcher wrapper.
# Handles Wayland/X11 detection and passes appropriate Electron/Chromium flags.

set -euo pipefail

BITWARDEN_DIR=/usr/lib/bitwarden

FLAGS=()

# Enable native Wayland rendering when the session is Wayland.
# The "auto" hint lets Electron choose the best platform (Wayland or X11)
# based on the runtime environment.
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    FLAGS+=(
        --ozone-platform-hint=auto
        --enable-features=WaylandWindowDecorations
    )
fi

# Allow users to pass extra Electron/Chromium flags via environment.
# Example: BITWARDEN_FLAGS="--disable-gpu" bitwarden
if [ -n "${BITWARDEN_FLAGS:-}" ]; then
    # shellcheck disable=SC2206
    FLAGS+=($BITWARDEN_FLAGS)
fi

exec "${BITWARDEN_DIR}/bitwarden" "${FLAGS[@]}" "$@"
