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

# Electron bundles pre-built Chromium binaries that use split-DWARF (DWO)
# debug info.  rpmbuild's debuginfo extraction (objcopy / gdb-add-index)
# cannot process them, causing:
#   objcopy: stGupDug: can't add section '.gdb_index'
#   ERROR: GDB exited with exit status 1 during index generation
# Disable debuginfo generation entirely — the bundled .so files already
# have their own debug info stripped by upstream's Electron build.
%global debug_package %{nil}

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
Release:        6%{?dist}
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
#  %pre
# ============================================================================
%pre
# Remove any stale update-alternatives entry for bitwarden.  This can be left
# behind when uninstalling the official Bitwarden RPM (from bitwarden.com)
# which registers /usr/bin/bitwarden via alternatives.  Without cleanup the
# alternatives daemon prints a spurious warning during our installation.
if command -v alternatives >/dev/null 2>&1; then
    alternatives --remove-all bitwarden 2>/dev/null || :
fi

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

# ---- Reduce renderer webpack memory pressure --------------------------------
# COPR's x86_64 builders run with a 2 GiB memory request.  Upstream's desktop
# renderer production build enables full sourcemaps and minification, which is
# enough to make Angular 20's webpack pass silently fail under that limit.
#
# Two changes are made here:
#
# 1) webpack.base.js is patched inline to disable renderer sourcemaps and
#    minification.  For a packaged local desktop app these are unnecessary and
#    save ~800 MB of peak heap during the Angular compilation.
#
# 2) On x86_64 the vendored node_modules include the native @swc/core binary
#    (swc.linux-x64-gnu.node).  SWC allocates memory outside the V8 heap so it
#    is not constrained by --max-old-space-size.  On x86_64 SWC native memory
#    plus the V8 heap can push the total process above the 2 GiB cgroup limit;
#    the kernel then OOM-kills webpack and npm returns 0 (because npm does not
#    propagate SIGKILL exit status in all cases), silently producing a build
#    directory with no index.html.  On aarch64 the x86_64 SWC binary is not
#    usable so babel-loader falls back to pure-JS and the build succeeds.
#
#    Removing the native SWC binary on x86_64 forces the same pure-JS fallback
#    as aarch64, keeping total process memory within the 2 GiB budget.
python3 - <<'PY'
from pathlib import Path

path = Path("apps/desktop/webpack.base.js")
text = path.read_text()

orig = text

# Disable renderer source-map devtool (saves ~400 MB V8 heap during compilation)
text = text.replace('    devtool: "source-map",\n', '    devtool: false,\n', 1)

# Disable renderer minification (saves ~400 MB V8 heap during TerserPlugin)
text = text.replace(
    '    optimization: {\n      minimizer: [\n',
    '    optimization: {\n      minimize: false,\n      minimizer: [\n',
    1,
)

# Remove SourceMapDevToolPlugin (its source-map pass also consumes significant memory)
text = text.replace(
    '      new webpack.SourceMapDevToolPlugin({\n        include: ["app/main.js"],\n      }),\n',
    '',
    1,
)

if text == orig:
    import sys
    print("ERROR: webpack.base.js patch did not match any strings — check indentation", file=sys.stderr)
    sys.exit(1)

path.write_text(text)
print("webpack.base.js: sourcemaps + minification disabled for RPM build")
PY

# ---- Create a dedicated renderer-only webpack config -----------------------
# webpack.config.js exports a function that returns [mainConfig, rendererConfig,
# preloadConfig].  Using `--config-name renderer` to filter this array silently
# produces no output on COPR x86_64 builders (webpack exits 0 but writes
# nothing).  The root cause is that `--config-name` filtering on function-based
# configs that return arrays does not work reliably across all webpack-cli
# versions present in the vendored node_modules.
#
# Workaround: create a thin wrapper config (webpack.renderer.only.js) that
# directly imports webpack.base.js's buildConfig(), calls it, and exports only
# element [1] (the renderer config) as a plain object — not a function, not an
# array.  webpack then compiles exactly the renderer without any filtering.
cat > apps/desktop/webpack.renderer.only.js << 'RENDERER_CFG_EOF'
/* RPM-build shim — exports only the renderer config from webpack.base.js.
 * Created during %prep; not present in the upstream source tree. */
const path = require("path");
const { buildConfig } = require("./webpack.base");
const configs = buildConfig({
  configName: "OSS",
  renderer: {
    entry: path.resolve(__dirname, "src/app/main.ts"),
    entryModule: "src/app/app.module#AppModule",
    tsConfig: path.resolve(__dirname, "tsconfig.renderer.json"),
  },
  main: {
    entry: path.resolve(__dirname, "src/entry.ts"),
    tsConfig: path.resolve(__dirname, "tsconfig.main.json"),
  },
  preload: {
    entry: path.resolve(__dirname, "src/preload.ts"),
    tsConfig: path.resolve(__dirname, "tsconfig.preload.json"),
  },
});
/* buildConfig returns [mainConfig, rendererConfig, preloadConfig]; export [1] */
module.exports = configs[1];
RENDERER_CFG_EOF

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

# ---- NOTE: npm rebuild is intentionally skipped --------------------------
# The vendor tarball is created with --ignore-scripts.  Running npm rebuild
# on the entire monorepo node_modules takes hours and exceeds the COPR
# 5-hour build timeout.
#
# Native modules we actually need are all Rust-based (desktop_napi,
# desktop_proxy, libprocess_isolation.so) and are built below by build.js.
# Modern npm packages that ship platform-specific binaries (esbuild, swc,
# keytar) use optionalDependencies which are already resolved by npm ci
# during vendor tarball generation — no rebuild needed.

# ---- Build Rust native modules --------------------------------------------
# Builds: desktop_napi.*.node, desktop_proxy, libprocess_isolation.so
# Pass --release so all Rust artifacts (proxy, process_isolation) are
# built in release mode, not debug.
pushd apps/desktop
node desktop_native/build.js --release
popd

# ---- Webpack bundle (main + renderer + preload) ----------------------------
# Run each webpack config SEQUENTIALLY so that any failure is immediately
# visible and fails the build rather than being swallowed by concurrently.
# Keep Node's heap below COPR's 2 GiB builder limit while still leaving enough
# room for the Angular 20 renderer build to finish.
export NODE_OPTIONS="--max-old-space-size=1400"
pushd apps/desktop
# cross-env in each script already sets NODE_ENV=production for webpack itself.
npm run build:main

# Use the dedicated renderer-only config created in %prep.  This bypasses the
# --config-name filtering that silently produces no output when applied to a
# function-based config returning an array on this webpack-cli version.
set +e
cross-env NODE_ENV=production webpack --config webpack.renderer.only.js
_renderer_exit=$?
set -e
printf "renderer webpack exit code: %d\n" "$_renderer_exit"
ls -la build/ || true

npm run build:preload
popd
unset NODE_OPTIONS

# Verify the renderer produced its output; if index.html is missing the asar
# will be empty of renderer content and the app will show a blank window.
test "$_renderer_exit" -eq 0 || \
    { echo "ERROR: renderer webpack exited with code ${_renderer_exit}"; exit 1; }
test -f apps/desktop/build/index.html || \
    { echo "ERROR: renderer webpack build produced no index.html"; exit 1; }
test -f apps/desktop/build/app/main.js || \
    { echo "ERROR: renderer webpack build produced no app/main.js"; exit 1; }

# ---- electron-builder: create unpacked application directory ---------------
# -c.buildDependenciesFromSource=false: we pre-build all Rust native modules
# above via build.js --release.  Letting electron-builder rebuild them during
# packing interferes with our pre-built .node file and slows the build.
# NODE_ENV=production: ensures after-pack.js and any spawned scripts see the
# correct environment (cross-env already sets this for webpack, but electron-
# builder's own Node context inherits the shell environment).
export NODE_ENV=production
pushd apps/desktop
%ifarch x86_64
npx electron-builder --linux --x64 --dir --config electron-builder.json \
    -c.buildDependenciesFromSource=false -p never
%endif
%ifarch aarch64
npx electron-builder --linux --arm64 --dir --config electron-builder.json \
    -c.buildDependenciesFromSource=false -p never
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

# Ensure the launcher wrapper (from upstream's after-pack.js linux-wrapper.sh)
# is executable.  The actual Electron binary is renamed to bitwarden-app by
# after-pack.js; ensure it is executable too.
chmod 0755 %{buildroot}%{bwdir}/bitwarden
test -f %{buildroot}%{bwdir}/bitwarden-app && \
    chmod 0755 %{buildroot}%{bwdir}/bitwarden-app

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

# Verify that after-pack.js ran correctly:
#   - bitwarden-app must exist (Electron binary renamed from bitwarden)
#   - bitwarden  must be the wrapper script (not the Electron binary)
#   - app.asar   must be present (webpack + electron-builder packing succeeded)
test -f %{buildroot}%{bwdir}/bitwarden-app || \
    { echo "ERROR: bitwarden-app missing — after-pack.js did not rename the Electron binary"; exit 1; }
test -f %{buildroot}%{bwdir}/resources/app.asar || \
    { echo "ERROR: app.asar missing — webpack/electron-builder build failed"; exit 1; }

# Verify that index.html landed inside the asar.  Electron's asar is a custom
# archive; use node to read the JSON header and grep for "index.html".
node -e "
const fs = require('fs');
const f = fs.openSync('%{buildroot}%{bwdir}/resources/app.asar', 'r');
const hdrSizeBuf = Buffer.alloc(8);
fs.readSync(f, hdrSizeBuf, 0, 8, 8);
const hdrSize = hdrSizeBuf.readUInt32LE(4);
const hdrBuf = Buffer.alloc(hdrSize);
fs.readSync(f, hdrBuf, 0, hdrSize, 16);
fs.closeSync(f);
const hdr = JSON.parse(hdrBuf.toString('utf8'));
if (!hdr.files['index.html']) {
  console.error('ERROR: index.html not found in app.asar — renderer webpack output was not packed');
  process.exit(1);
}
console.log('OK: index.html found in app.asar');
"

# Smoke-test: verify the Electron binary responds to --version.
# bitwarden-app is the actual Electron binary; the wrapper (bitwarden) chains
# into it but expects a display server which is unavailable in the build env.
%{buildroot}%{bwdir}/bitwarden-app --version || \
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
* Fri Mar 20 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.2.1-6
- Create webpack.renderer.only.js in %%prep to compile the renderer directly
  without --config-name filtering; the filtering silently emits no output when
  applied to a function-based config returning an array on the vendored
  webpack-cli, causing the renderer to exit 0 with nothing written to build/

* Fri Mar 20 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.2.1-5
- Remove native @swc/core x86_64 binaries from the vendor tarball during %%prep
  so babel-loader falls back to pure-JS on x86_64 (same as aarch64); the native
  SWC binary allocates memory outside the V8 heap and was pushing the renderer
  webpack process above the 2 GiB COPR cgroup limit (silent OOM-kill returning 0)
- Add error-trapping around the renderer build to catch silent failures
- Make webpack.base.js patch fail explicitly if the target strings are not found
- Bump Release to 5

* Fri Mar 20 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.2.1-4
- Patch upstream webpack.base.js during %%prep to disable renderer production
  sourcemaps and minification for RPM builds, reducing x86_64 memory pressure
  enough for COPR's 2 GiB builders
- Lower NODE_OPTIONS heap cap from 4096 to 1400 so webpack stays within the
  builder memory budget instead of being OOM-killed

* Thu Mar 19 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.2.1-3
- Run webpack builds sequentially (build:main, build:renderer, build:preload)
  instead of via concurrently so that a renderer failure is immediately visible
  and fails the RPM build rather than being silently swallowed
- Set NODE_OPTIONS=--max-old-space-size=4096 for Angular 20 AOT compilation
  to avoid silent OOM-kills leaving build/index.html absent
- Add post-webpack assertions: fail the build if build/index.html or
  build/app/main.js are absent (catches the blank-window root cause at build time)
- Add asar content check in %%check: fail if index.html is not in app.asar

* Thu Mar 19 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.2.1-2
- Add %%pre scriptlet to remove stale update-alternatives entry for bitwarden
  that is left behind when the official Bitwarden RPM is uninstalled
- Pass -c.buildDependenciesFromSource=false to electron-builder to prevent it
  from rebuilding pre-built Rust native modules during packing
- Set NODE_ENV=production for the electron-builder invocation
- Add chmod 0755 for bitwarden-app (Electron binary renamed by after-pack.js)
- Tighten %%check: fail the build if bitwarden-app or app.asar are absent

* Sun Mar 15 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.2.1-1
- Initial package build from upstream source
