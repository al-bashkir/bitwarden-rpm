# bitwarden-rpm

RPM packaging for [Bitwarden Desktop](https://bitwarden.com) — built from
upstream source for Fedora via COPR.

## Quick start

```bash
# 1. Generate vendor tarballs (requires network, Node.js >= 22, Rust, cargo)
./generate-vendor-tarball.sh 2026.2.1

# 2. Download remaining sources
spectool -g -R bitwarden.spec

# 3. Build SRPM
rpmbuild -bs bitwarden.spec

# 4. Build in mock
mock -r fedora-rawhide-x86_64 --rebuild ~/rpmbuild/SRPMS/bitwarden-*.src.rpm
```

## Architecture support

| Arch | Status |
|------|--------|
| x86_64 | Supported |
| aarch64 | Supported (requires arch-specific vendor tarball) |

## Files

| File | Purpose |
|------|---------|
| `bitwarden.spec` | RPM spec file |
| `bitwarden.sh` | Launcher wrapper script |
| `com.bitwarden.desktop.desktop` | XDG desktop entry |
| `com.bitwarden.desktop.metainfo.xml` | AppStream metadata |
| `generate-vendor-tarball.sh` | Offline dependency vendoring script |
| `.copr/Makefile` | COPR SCM build integration |
| `AGENTS.md` | Maintenance guide for packagers and agents |

## License

Packaging files in this repository are licensed under GPL-3.0-only, consistent
with the upstream Bitwarden Desktop application.
