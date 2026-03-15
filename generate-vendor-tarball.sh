#!/usr/bin/bash
# ============================================================================
# generate-vendor-tarball.sh — create offline dependency tarballs for
# Bitwarden Desktop RPM build.
#
# This script MUST be run on a machine with:
#   - network access (downloads source + dependencies)
#   - Node.js >= 22, npm ~10
#   - Rust stable + cargo
#   - zstd
#
# The output tarballs are architecture-specific for the node vendor tarball
# (npm resolves platform-specific optional dependencies).  Run this script
# on EACH target architecture, or only on the architecture you intend to
# build for.
#
# Usage:
#   ./generate-vendor-tarball.sh <version>
#
# Example:
#   ./generate-vendor-tarball.sh 2026.2.1
#
# Outputs (in current directory):
#   bitwarden-<version>-node-vendor.tar.zst
#   bitwarden-<version>-cargo-vendor.tar.zst
# ============================================================================
set -euo pipefail

VERSION="${1:?Usage: $0 <version>}"
TAG="desktop-v${VERSION}"
REPO="bitwarden/clients"
WORKDIR="$(mktemp -d)"
OUTDIR="$(pwd)"

cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

echo "==> Working directory: ${WORKDIR}"
echo "==> Target version:    ${VERSION} (tag: ${TAG})"

# ---------- Download upstream source ----------------------------------------
echo "==> Downloading upstream source tarball..."
curl -fSL -o "${WORKDIR}/source.tar.gz" \
    "https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"

echo "==> Extracting source..."
tar -xzf "${WORKDIR}/source.tar.gz" -C "${WORKDIR}"
SRCDIR="${WORKDIR}/clients-${TAG}"

if [ ! -d "${SRCDIR}" ]; then
    echo "ERROR: expected directory ${SRCDIR} not found after extraction"
    echo "       Check that the tag '${TAG}' exists and the archive layout matches."
    exit 1
fi

# ---------- Install npm dependencies (offline-friendly) ---------------------
echo "==> Installing npm dependencies (--ignore-scripts for arch portability)..."
pushd "${SRCDIR}" > /dev/null

# --ignore-scripts: skips postinstall hooks (electron download, native
# compilation).  This makes the tarball smaller and avoids downloading
# the Electron binary (provided separately in the spec as Source3/Source4).
#
# NOTE: platform-specific optional deps (e.g., @esbuild/linux-x64) ARE
# resolved and installed by npm based on the current platform.  This makes
# the resulting tarball architecture-specific.
npm ci --ignore-scripts 2>&1

popd > /dev/null

# ---------- Create node vendor tarball --------------------------------------
echo "==> Creating node vendor tarball..."
tar -C "${SRCDIR}" --zstd -cf "${OUTDIR}/bitwarden-${VERSION}-node-vendor.tar.zst" \
    node_modules/

echo "    -> bitwarden-${VERSION}-node-vendor.tar.zst"

# ---------- Vendor Cargo dependencies ---------------------------------------
echo "==> Vendoring Cargo dependencies..."
pushd "${SRCDIR}/apps/desktop/desktop_native" > /dev/null

mkdir -p .cargo
# cargo vendor outputs a TOML snippet that must be placed in .cargo/config.toml
cargo vendor --versioned-dirs cargo-vendor 2>/dev/null | tee .cargo/config.toml

popd > /dev/null

# ---------- Create cargo vendor tarball -------------------------------------
echo "==> Creating cargo vendor tarball..."
tar -C "${SRCDIR}/apps/desktop/desktop_native" --zstd -cf \
    "${OUTDIR}/bitwarden-${VERSION}-cargo-vendor.tar.zst" \
    cargo-vendor/ .cargo/

echo "    -> bitwarden-${VERSION}-cargo-vendor.tar.zst"

# ---------- Print summary ---------------------------------------------------
echo ""
echo "=== Vendor tarballs generated successfully ==="
echo ""
echo "  bitwarden-${VERSION}-node-vendor.tar.zst   (arch: $(uname -m))"
echo "  bitwarden-${VERSION}-cargo-vendor.tar.zst   (arch: any)"
echo ""
echo "Place these files alongside bitwarden.spec in your SOURCES directory."
echo ""
echo "Electron version in upstream: check apps/desktop/electron-builder.json"
echo "  electronVersion field, and update %global electron_ver in the spec."
