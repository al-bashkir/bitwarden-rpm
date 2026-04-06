# ---------------------------------------------------------------------------
# Bitwarden CLI (bw) — Fedora/COPR RPM Spec
# ---------------------------------------------------------------------------
#
# Pre-built binary package.  No source compilation is required.
# The upstream release is a self-contained pkg-bundled Node.js executable
# published on GitHub Releases.  Shell completions are generated from the
# binary during %%build.
#
# Only ZSH completion is supported by this version of the CLI.
# Upstream completion.command.ts has validShells = ["zsh"] — bash is not
# implemented.  The completion file is installed to the standard Fedora path
# /usr/share/zsh/site-functions/_bw.
#
# To update: change Version and rebuild the SRPM.  No vendor tarballs are
# needed — the only Source is the prebuilt zip from GitHub Releases.
# ---------------------------------------------------------------------------

%global debug_package %{nil}

# The bw binary is a pkg-bundled Node.js executable.  It embeds a virtual
# filesystem snapshot at a known byte offset inside itself and reads it back
# via /proc/self/exe at runtime.  Stripping the binary shifts that offset,
# causing the runtime error "Pkg: Error reading from file."  Disable strip.
%define __strip /bin/true

%global cli_tag     cli-v%{version}

Name:           bw
Version:        2026.3.0
Release:        2%{?dist}
Summary:        Bitwarden Password Manager CLI

License:        GPL-3.0-only
URL:            https://bitwarden.com
VCS:            https://github.com/bitwarden/clients

# Prebuilt CLI binary for aarch64.
# Source URL pattern: bw-linux-arm64-<VERSION>.zip
Source0:        https://github.com/bitwarden/clients/releases/download/%{cli_tag}/bw-linux-arm64-%{version}.zip

# ---- Architecture ---------------------------------------------------------
# This package targets aarch64 only.  An x86_64 build is available upstream
# (bw-linux-<VERSION>.zip) but is not included here to keep parity with the
# bitwarden desktop package in this repo.
ExclusiveArch:  aarch64

# ---- Build Dependencies ---------------------------------------------------
BuildRequires:  unzip

# ---- Runtime Dependencies --------------------------------------------------
# The binary is a self-contained pkg-bundled executable.  It statically
# bundles its Node.js runtime and only requires base glibc/libstdc++ which
# are always present on any Fedora installation.

%description
The Bitwarden command-line interface (CLI) is a powerful, fully-featured
tool for accessing and managing your Bitwarden vault.  Most features found
in other Bitwarden client applications (desktop, browser extension, etc.)
are available from the CLI.

This package distributes the prebuilt %{name} binary for aarch64 Linux as
published by Bitwarden, Inc. on GitHub Releases.

# ============================================================================
#  %prep
# ============================================================================
%prep
# Use -c to create a build subdirectory; -T to skip auto-extraction of Source0
# (the zip is not a standard tarball that %%setup can unpack directly).
%setup -c -T
# The zip contains a single bare executable named bw; extract it here.
unzip -j %{SOURCE0} bw

# ============================================================================
#  %build
# ============================================================================
%build
chmod 0755 bw

# Generate ZSH shell completion.
# Upstream only supports zsh (validShells = ["zsh"] in completion.command.ts).
# The output is written to _bw (conventional zsh completion file name).
./bw completion --shell zsh > _bw

# Fail loudly if the completion output is empty.
test -s _bw || { echo "ERROR: bw completion --shell zsh produced no output"; exit 1; }

# ============================================================================
#  %install
# ============================================================================
%install
# Binary
install -Dpm 0755 bw %{buildroot}%{_bindir}/%{name}

# ZSH completion — standard Fedora location
install -Dpm 0644 _bw \
    %{buildroot}%{_datadir}/zsh/site-functions/_%{name}

# ============================================================================
#  %check
# ============================================================================
%check
# Smoke-test: verify the binary responds to --version in the build chroot.
./bw --version

# ============================================================================
#  %files
# ============================================================================
%files
%{_bindir}/%{name}
%{_datadir}/zsh/site-functions/_%{name}

%changelog
* Mon Apr 06 2026 Aksenov Pavel <41126916+al-bashkir@users.noreply.github.com> - 2026.3.0-1
- Initial package for Bitwarden CLI prebuilt binary
