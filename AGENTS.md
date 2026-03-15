# Bitwarden Desktop RPM — Maintainer / Agent Guide

## Package purpose

RPM package of [Bitwarden Desktop](https://bitwarden.com) for Fedora, built
from upstream source and distributed via COPR.  JavaScript (webpack) and Rust
(napi-rs + proxy binary) code are compiled during the build; the Electron
runtime is bundled as a prebuilt binary because Fedora does not package
Electron.

## Upstream source

| Item | Value |
|------|-------|
| Repository | <https://github.com/bitwarden/clients> |
| Desktop app path | `apps/desktop/` |
| Rust native code | `apps/desktop/desktop_native/` |
| Tag format | `desktop-v<YEAR>.<MONTH>.<PATCH>` |
| Releases page | <https://github.com/bitwarden/clients/releases> |
| Source archive URL | `https://github.com/bitwarden/clients/archive/refs/tags/desktop-v<VERSION>.tar.gz` |
| Extracted dir name | `clients-desktop-v<VERSION>/` |

**To find the latest desktop release**: filter the releases page by tags
starting with `desktop-v`.  Ignore `browser-v*`, `cli-v*`, `web-v*` etc.

## How to update the package

### 1. Update version-sensitive fields in `bitwarden.spec`

```
%global electron_ver    <new Electron version>   ← from electron-builder.json "electronVersion"
Version:        <new upstream version>            ← e.g. 2026.3.0
Release:        1%{?dist}                         ← reset to 1 on version bump
```

### 2. Find the new Electron version

Open `apps/desktop/electron-builder.json` on the release tag and read the
`"electronVersion"` field.  Update `%global electron_ver` in the spec.

### 3. Update Source0 implicitly

`Source0` uses `%{version}` and `%{desktop_tag}`, so changing `Version:`
automatically updates the download URL.  Verify with:

```bash
spectool -g -n bitwarden.spec
```

### 4. Regenerate vendor tarballs

```bash
./generate-vendor-tarball.sh <new-version>
```

This creates two files in the current directory:
- `bitwarden-<VERSION>-node-vendor.tar.zst` (arch-specific!)
- `bitwarden-<VERSION>-cargo-vendor.tar.zst` (arch-independent)

**Multi-arch note**: the node vendor tarball is architecture-specific because
npm resolves platform-specific optional dependencies (e.g., `@esbuild/linux-x64`
vs `@esbuild/linux-arm64`).  If building for both x86_64 and aarch64, run
the vendor script on each architecture.

### 5. Update `%changelog` and metainfo `<releases>`

- Add a new `%changelog` entry in the spec.
- Add a new `<release>` element in `com.bitwarden.desktop.metainfo.xml`.

### 6. Verify locally

```bash
# Lint the spec
rpmlint bitwarden.spec

# Download all sources
spectool -g -R bitwarden.spec

# Test build in mock (Fedora rawhide example)
mock -r fedora-rawhide-x86_64 --rebuild bitwarden-<version>-1.fc42.src.rpm

# Validate the built RPM
rpmlint ~/rpmbuild/RPMS/x86_64/bitwarden-*.rpm
```

## Source and patch file inventory

| Source | File | Purpose | Update frequency |
|--------|------|---------|-----------------|
| Source0 | `desktop-v%{version}.tar.gz` | Upstream monorepo source | Every version |
| Source1 | `bitwarden-%{version}-node-vendor.tar.zst` | Vendored node_modules | Every version |
| Source2 | `bitwarden-%{version}-cargo-vendor.tar.zst` | Vendored Cargo crates | Every version |
| Source3 | `electron-v%{electron_ver}-linux-x64.zip` | Electron binary (x86_64) | When Electron version changes |
| Source4 | `electron-v%{electron_ver}-linux-arm64.zip` | Electron binary (aarch64) | When Electron version changes |
| Source10 | `bitwarden.sh` | Launcher wrapper script | Rarely |
| Source11 | `com.bitwarden.desktop.desktop` | XDG desktop entry | Rarely |
| Source12 | `com.bitwarden.desktop.metainfo.xml` | AppStream metadata | Every version (releases section) |

**Patches**: none currently.  If upstream introduces breaking changes for the
offline/Fedora build, patches may be needed.  Common candidates:
- Webpack config changes that break without network
- `build.js` (Rust build orchestrator) assuming specific Rust toolchain features
- `electron-builder.json` format changes
- New native dependencies not covered by BuildRequires

## Frequently breaking areas on upstream update

1. **`electron-builder.json` `electronVersion`** — must match `%global electron_ver`.
   If forgotten, electron-builder downloads the wrong (or no) Electron binary.

2. **Node.js version requirement** — upstream `engines.node` may bump.  Check
   root `package.json`.  Fedora must ship a matching Node.js.

3. **Rust crate additions** — new Cargo dependencies may appear.  Regenerating
   the cargo vendor tarball handles this automatically, but new *system* library
   dependencies (linked via `-sys` crates) require new `BuildRequires` entries.

4. **New workspace packages in the monorepo** — if upstream adds new `libs/`
   packages that the desktop app depends on, npm workspace resolution should
   handle it, but verify that workspace symlinks in node_modules are intact.

5. **electron-builder hooks** (`scripts/before-pack.js`, `after-pack.js`) —
   these may copy files or modify the output in ways that affect `%install`.
   Review after each update.

6. **Unpacked directory name** — electron-builder uses `linux-unpacked` for
   x86_64 and `linux-arm64-unpacked` for aarch64.  If this convention changes,
   update the `%ifarch` blocks in `%build` and `%install`.

## Desktop integration checks

After building, verify:

```bash
# Desktop file validates
desktop-file-validate /usr/share/applications/com.bitwarden.desktop.desktop

# AppStream metadata validates
appstream-util validate-relax --nonet \
    /usr/share/metainfo/com.bitwarden.desktop.metainfo.xml

# Icons are installed in hicolor
ls /usr/share/icons/hicolor/*/apps/com.bitwarden.desktop.png

# The wrapper script works
bitwarden --version

# The .desktop file launches the app (manual test)
gtk-launch com.bitwarden.desktop
```

## SELinux behavior

Bitwarden Desktop runs as an unprivileged Electron application:

- **No custom SELinux policy is needed.**
- The `chrome-sandbox` SUID binary is removed during `%install`; Fedora
  enables user namespaces (`kernel.unprivileged_userns_clone=1`) by default,
  providing unprivileged sandboxing.
- The application runs in the user's SELinux context (`unconfined_t` for
  interactive desktop sessions).
- Network access is the normal `http_port_t` outbound to Bitwarden servers.
- No file context overrides, no `restorecon`, no `chcon`, no `setsebool`.

If a future version adds a system-level daemon (e.g., native messaging host
as a systemd service), create a `-selinux` subpackage with a proper Type
Enforcement (`.te`) module.

## Prohibited practices

The following MUST NOT be done when maintaining this package:

| Prohibition | Reason |
|-------------|--------|
| Network access in `%prep`, `%build`, `%install` | COPR/mock sandbox forbids it; violates Fedora policy |
| `curl`/`wget` in spec scriptlets | Same as above |
| Downloading in `%build` via npm/cargo | Use vendored tarballs |
| Packaging prebuilt binaries without source build | Violates packaging guidelines for COPR; only Electron itself is exempt (no system package exists) |
| `chmod 4755` on chrome-sandbox | Use user namespaces instead |
| `chcon` / `restorecon` / `setsebool` in scriptlets | Violates SELinux packaging guidelines |
| Disabling SELinux (`setenforce 0`) | Never |
| `%global _build_id_links none` hacks | Fix the root cause instead |
| Bundling the entire `node_modules/` in the installed RPM | Only the webpack-bundled `app.asar` and native binaries are installed |
| Running commands that require a display (GUI) in `%build`/`%check` | Build environment is headless |

## COPR configuration

### Single architecture (simplest)

1. Create a COPR project.
2. Add this git repo as an SCM source with "Make SRPM" method.
3. Set `.copr/Makefile` as the makefile path.
4. Enable only the architectures matching your vendor tarball.

### Multi-architecture

The node vendor tarball is arch-specific.  Options:

**Option A — COPR Custom method** (recommended):
Write a custom script that detects `uname -m` and generates the correct vendor
tarball.  The Custom method runs the script per-chroot.

**Option B — manual SRPM upload**:
Run `generate-vendor-tarball.sh` on each arch, build SRPMs locally, and upload
them to COPR separately.

**Option C — fat vendor tarball**:
Modify the vendor script to install platform-specific optional npm packages for
ALL target architectures.  This produces a larger but universal tarball.  Requires
manual maintenance of the platform package list.

## File layout (installed)

```
/usr/bin/bitwarden                                  ← wrapper script
/usr/lib/bitwarden/                                 ← Electron app bundle
/usr/lib/bitwarden/bitwarden                        ← Electron binary
/usr/lib/bitwarden/resources/app.asar               ← webpack-bundled app
/usr/lib/bitwarden/desktop_proxy                    ← Rust IPC binary
/usr/lib/bitwarden/libprocess_isolation.so          ← Rust sandbox library
/usr/share/applications/com.bitwarden.desktop.desktop
/usr/share/icons/hicolor/*/apps/com.bitwarden.desktop.png
/usr/share/metainfo/com.bitwarden.desktop.metainfo.xml
```
