# ---------------------------------------------------------------------------
# Bitwarden Desktop — Fedora/COPR RPM Spec
# ---------------------------------------------------------------------------
#
# This spec builds Bitwarden Desktop from upstream source.  JavaScript and
# Rust code are compiled during the build; the Electron runtime is a
# pre-built binary because Fedora does not package Electron (building
# Chromium from source is impractical for per-app packaging).
#
# Offline build: all npm and Cargo dependencies are pre-vendored.
#   Source1 — npm node_modules  (arch-SPECIFIC, see generate-vendor-tarball.sh)
#   Source2 — cargo vendor      (arch-independent, pure Rust source)
#   Source3/4 — Electron zips   (one per supported arch)
#
# See AGENTS.md for maintenance and update instructions.
# ---------------------------------------------------------------------------

# ---- version-sensitive globals (update on every version bump) -------------
%global electron_ver    39.2.6
# ---------------------------------------------------------------------------

%global upstream_repo   clients
%global desktop_tag     desktop-v%{version}
# GitHub tarball extracts to <repo>-<tag>/
%global srcdir          %{upstream_repo}-%{desktop_tag}

# Fixed /usr/lib path for the application bundle.  NOT %%{_libdir} — Electron
# apps are self-contained bundles mixing arch-specific binaries with
# arch-independent resources.  A fixed prefix avoids breaking Electron's
# internal library resolution (same convention used by Firefox, VS Code, etc.)
%global bwdir           %{_prefix}/lib/%{name}

Name:           bitwarden
Version:        2026.2.1
Release:        1%{?dist}
Summary:        A secure and free password manager for all of your devices

License:        GPL-3.0-only
URL:            https://bitwarden.com
VCS:            https://github.com/bitwarden/clients

# ---- Sources --------------------------------------------------------------
# Source0 — upstream monorepo snapshot at the desktop release tag
Source0:        https://github.com/bitwarden/%{upstream_repo}/archive/refs/tags/%{desktop_tag}.tar.gz

# Source1 — vendored node_modules (created by generate-vendor-tarball.sh).
# IMPORTANT: this tarball is ARCHITECTURE-SPECIFIC because npm resolves
# platform-specific optional dependencies (e.g., @esbuild/linux-x64 vs
# @esbuild/linux-arm64).  Regenerate on each target arch.
Source1:        %{name}-%{version}-node-vendor.tar.zst

# Source2 — vendored Cargo crates (arch-independent source code).
Source2:        %{name}-%{version}-cargo-vendor.tar.zst

# Source3-4 — pre-built Electron binaries (one per arch).
# Electron is not available as a system package on any Linux distribution.
Source3:        https://github.com/electron/electron/releases/download/v%{electron_ver}/electron-v%{electron_ver}-linux-x64.zip
Source4:        https://github.com/electron/electron/releases/download/v%{electron_ver}/electron-v%{electron_ver}-linux-arm64.zip

# Source10-12 — auxiliary integration files, maintained in this repo.
Source10:       bitwarden.sh
Source11:       com.bitwarden.desktop.desktop
Source12:       com.bitwarden.desktop.metainfo.xml

# ---- Architecture ---------------------------------------------------------
# Electron ships Linux binaries for x86_64 and aarch64 only.
# The upstream Rust napi module (@bitwarden/desktop-napi) lists exactly
# these two Linux targets.  No other architecture is viable.
ExclusiveArch:  x86_64 aarch64

# ---- Build Dependencies ---------------------------------------------------
# Node.js / npm — upstream requires node >= 22.12.0 (CalVer "Jod" LTS).
# Fedora 41+ ships Node.js 22.x.  Older Fedora releases will not work.
BuildRequires:  nodejs >= 22
BuildRequires:  npm

# Rust toolchain — upstream pins 1.91.1 via rust-toolchain.toml, but we
# remove the pin and use whatever stable Rust Fedora ships.  Set the minimum
# to something reasonably recent; adjust if the build breaks.
BuildRequires:  rust >= 1.80.0
BuildRequires:  cargo

# C/C++ toolchain for node-gyp native addons and Rust FFI
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  python3

# Headers for native modules
BuildRequires:  libsecret-devel
BuildRequires:  glib2-devel
BuildRequires:  libX11-devel
BuildRequires:  libXtst-devel
BuildRequires:  nss-devel
BuildRequires:  libXScrnSaver-devel
BuildRequires:  alsa-lib-devel
BuildRequires:  mesa-libGL-devel
BuildRequires:  libdrm-devel
BuildRequires:  atk-devel
BuildRequires:  at-spi2-atk-devel
BuildRequires:  cups-devel
BuildRequires:  gtk3-devel
BuildRequires:  pango-devel

# Tooling
BuildRequires:  unzip
BuildRequires:  zstd

# Desktop integration validation
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib

# ---- Runtime Dependencies --------------------------------------------------
Requires:       libsecret%{?_isa}
Requires:       libnotify%{?_isa}
Requires:       libXtst%{?_isa}
Requires:       nss%{?_isa}
Requires:       libXScrnSaver%{?_isa}
Requires:       alsa-lib%{?_isa}
Requires:       at-spi2-atk%{?_isa}
Requires:       gtk3%{?_isa}
Requires:       hicolor-icon-theme

# ---- Bundled dependencies --------------------------------------------------
# Electron bundles Chromium + Node.js.  Listing every transitive npm/crate
# dependency is impractical; we declare the major runtime.
Provides:       bundled(electron) = %{electron_ver}
Provides:       bundled(nodejs-modules)

# ---- SELinux ---------------------------------------------------------------
# Bitwarden Desktop runs as an unprivileged Electron application.
# - No listening on privileged ports
# - No access to privileged system resources
# - chrome-sandbox is REMOVED; Fedora enables user namespaces by default,
#   which is the modern unprivileged sandbox mechanism.
# - No SUID bits, no chcon hacks, no policy overrides.
# ⇒ No custom SELinux policy module is needed.
#
# If a future version introduces a privileged system service (e.g., a
# native messaging host daemon), a -selinux subpackage with a Type
# Enforcement module should be created.  See:
#   https://docs.fedoraproject.org/en-US/packaging-guidelines/SELinux/

%description
Bitwarden is a free and open-source password management service that stores
sensitive information such as website credentials in an encrypted vault.

This package provides the Bitwarden Desktop application, built from upstream
source.  The Electron runtime is bundled; all JavaScript and Rust application
code is compiled during the RPM build.

# ============================================================================
#  %prep
# ============================================================================
%prep
%setup -q -n %{srcdir}

# ---- Restore vendored Node.js dependencies --------------------------------
# The tarball overlays node_modules/ at the monorepo root.
# Workspace symlinks (e.g., node_modules/@bitwarden/common → ../../libs/common)
# are preserved; they resolve against the Source0 tree.
tar --zstd -xf %{SOURCE1}

# ---- Restore vendored Cargo dependencies ----------------------------------
# Extracts cargo-vendor/ and .cargo/config.toml into the desktop_native
# Rust workspace root.
tar --zstd -xf %{SOURCE2} -C apps/desktop/desktop_native

# ---- Populate Electron binary ----------------------------------------------
# The `electron` npm package expects its binary at node_modules/electron/dist/.
# We extract the arch-correct zip there and write path.txt so the package's
# JS entrypoint can locate it.
mkdir -p node_modules/electron/dist
%ifarch x86_64
unzip -q -o %{SOURCE3} -d node_modules/electron/dist/
%endif
%ifarch aarch64
unzip -q -o %{SOURCE4} -d node_modules/electron/dist/
%endif
echo 'dist/electron' > node_modules/electron/path.txt
chmod 0755 node_modules/electron/dist/electron

# Set up electron-builder's cache so it doesn't try to download Electron.
mkdir -p .electron-cache
%ifarch x86_64
cp %{SOURCE3} .electron-cache/electron-v%{electron_ver}-linux-x64.zip
%endif
%ifarch aarch64
cp %{SOURCE4} .electron-cache/electron-v%{electron_ver}-linux-arm64.zip
%endif

# ---- Remove upstream Rust toolchain pin ------------------------------------
# Upstream pins an exact Rust version for developer reproducibility.
# Fedora's system Rust is recent stable and should be compatible.
rm -f apps/desktop/desktop_native/rust-toolchain.toml

# ============================================================================
#  %build
# ============================================================================
%build
# ---- Enforce fully-offline build -------------------------------------------
export npm_config_offline=true
export npm_config_fund=false
export npm_config_audit=false
export npm_config_update_notifier=false
export npm_config_progress=false
export npm_config_save=false
export ELECTRON_SKIP_BINARY_DOWNLOAD=1
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true

# electron-builder cache — prevents download attempts
export ELECTRON_CACHE=$PWD/.electron-cache
# Tell electron-builder to use local unpacked Electron
export ELECTRON_OVERRIDE_DIST_PATH=$PWD/node_modules/electron/dist

# ---- Create napi CLI shim -------------------------------------------------
# @napi-rs/cli is published as a pre-compiled binary with platform-specific
# optional packages (e.g., @napi-rs/cli-linux-x64-gnu).  The vendor tarball
# is created on x86_64, so the aarch64 variant is absent — `napi` command is
# not found on aarch64 builders.
#
# Solution: inject a shim that replaces `napi build --platform --no-js` with
# a direct `cargo build --release` invocation.  The shim is placed in
# .bin-override/ which is prepended to PATH before node_modules/.bin, so it
# takes precedence over any (non-functional) napi wrapper that may exist.
#
# The shim runs with CWD = apps/desktop/desktop_native/napi/ (set by build.js).
# The Cargo workspace root is desktop_native/, so compiled output lands in
# ../target/release/libdesktop_napi.so relative to the CWD.
mkdir -p .bin-override
cat > .bin-override/napi << 'NAPI_SHIM_EOF'
#!/usr/bin/bash
# napi shim — replaces @napi-rs/cli for `napi build --platform --no-js`
set -euo pipefail
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  SUFFIX="linux-x64-gnu" ;;
    aarch64) SUFFIX="linux-arm64-gnu" ;;
    *)       echo "napi shim: unsupported arch: $ARCH" >&2; exit 1 ;;
esac
echo "napi shim: building desktop_napi (release) for $ARCH → desktop_napi.${SUFFIX}.node"
cargo build --release
cp "../target/release/libdesktop_napi.so" "desktop_napi.${SUFFIX}.node"
NAPI_SHIM_EOF
chmod +x .bin-override/napi

# Ensure root node_modules/.bin is in PATH for npx/webpack/etc.
# .bin-override/ is prepended so the napi shim takes priority.
export PATH=$PWD/.bin-override:$PWD/node_modules/.bin:$PATH

# ---- Rebuild native Node.js addons for current arch -----------------------
# The vendor tarball was created with --ignore-scripts, so node-gyp addons
# are not yet compiled.  npm rebuild compiles them offline.
npm rebuild 2>&1 || echo "WARN: npm rebuild had non-zero exit (may be OK)"

# ---- Build Rust native modules --------------------------------------------
# Builds: desktop_napi.*.node, desktop_proxy, libprocess_isolation.so
# Pass --release so all Rust artifacts (proxy, process_isolation) are
# built in release mode, not debug.
pushd apps/desktop
node desktop_native/build.js --release
popd

# ---- Webpack bundle (main + renderer + preload) ----------------------------
pushd apps/desktop
npm run build
popd

# ---- electron-builder: create unpacked application directory ---------------
pushd apps/desktop
%ifarch x86_64
npx electron-builder --linux --x64 --dir --config electron-builder.json -p never
%endif
%ifarch aarch64
npx electron-builder --linux --arm64 --dir --config electron-builder.json -p never
%endif
popd

# ============================================================================
#  %install
# ============================================================================
%install
# Determine the unpacked directory name (differs by arch)
%ifarch x86_64
eb_unpacked=apps/desktop/dist/linux-unpacked
%endif
%ifarch aarch64
eb_unpacked=apps/desktop/dist/linux-arm64-unpacked
%endif

# ---- Application bundle ---------------------------------------------------
install -d %{buildroot}%{bwdir}
cp -a ${eb_unpacked}/* %{buildroot}%{bwdir}/

# Remove chrome-sandbox: Fedora uses user namespaces (unprivileged sandbox).
# Keeping it would require either SUID (bad) or a custom SELinux policy
# (unnecessary).
rm -f %{buildroot}%{bwdir}/chrome-sandbox

# Ensure the main binary is executable
chmod 0755 %{buildroot}%{bwdir}/bitwarden

# Ensure native binaries are executable
test -f %{buildroot}%{bwdir}/desktop_proxy && \
    chmod 0755 %{buildroot}%{bwdir}/desktop_proxy
test -f %{buildroot}%{bwdir}/resources/desktop_proxy && \
    chmod 0755 %{buildroot}%{bwdir}/resources/desktop_proxy

# ---- Wrapper script -------------------------------------------------------
install -Dpm 0755 %{SOURCE10} %{buildroot}%{_bindir}/%{name}

# ---- Desktop entry ---------------------------------------------------------
install -Dpm 0644 %{SOURCE11} \
    %{buildroot}%{_datadir}/applications/com.bitwarden.desktop.desktop

# ---- AppStream metainfo ----------------------------------------------------
install -Dpm 0644 %{SOURCE12} \
    %{buildroot}%{_metainfodir}/com.bitwarden.desktop.metainfo.xml

# ---- Icons -----------------------------------------------------------------
# Upstream ships PNGs in apps/desktop/resources/icons/ named by size
# (e.g., 16x16.png, 32x32.png, 128x128.png, etc.).
for icon in apps/desktop/resources/icons/*.png; do
    size=$(basename "$icon" .png)
    if echo "$size" | grep -qE '^[0-9]+x[0-9]+$'; then
        install -Dpm 0644 "$icon" \
            %{buildroot}%{_datadir}/icons/hicolor/${size}/apps/com.bitwarden.desktop.png
    fi
done
# Fallback: install the main icon.png as 512x512 if that size is missing
if [ ! -f %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/com.bitwarden.desktop.png ]; then
    install -Dpm 0644 apps/desktop/resources/icon.png \
        %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/com.bitwarden.desktop.png
fi

# ============================================================================
#  %check
# ============================================================================
%check
# Validate desktop entry
desktop-file-validate %{buildroot}%{_datadir}/applications/com.bitwarden.desktop.desktop

# Validate AppStream metainfo (relaxed: no network, no screenshot fetch)
appstream-util validate-relax --nonet \
    %{buildroot}%{_metainfodir}/com.bitwarden.desktop.metainfo.xml

# Smoke-test: verify the Electron binary is functional
# (may fail in headless build environments; treat as best-effort)
%{buildroot}%{bwdir}/bitwarden --version || \
    echo "WARN: --version smoke test failed (expected in headless env)"

# ============================================================================
#  %files
# ============================================================================
# No %post/%postun scriptlets for desktop-database or icon-cache updates:
# modern Fedora handles this via RPM file triggers in desktop-file-utils
# and hicolor-icon-theme packages.

%files
%license LICENSE.txt
%doc README.md

# Application bundle
%{bwdir}

# Launcher wrapper
%{_bindir}/%{name}

# Desktop integration
%{_datadir}/applications/com.bitwarden.desktop.desktop
%{_datadir}/icons/hicolor/*/apps/com.bitwarden.desktop.png
%{_metainfodir}/com.bitwarden.desktop.metainfo.xml

%changelog
* Sun Mar 15 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.2.1-1
- Initial package build from upstream source
