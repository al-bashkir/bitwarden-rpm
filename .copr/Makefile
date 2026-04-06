# ============================================================================
# COPR Make SRPM — generates the source RPM for Bitwarden packages.
#
# COPR's "Make SRPM" SCM method clones this git repo on a builder and runs:
#   make -f .copr/Makefile srpm outdir=<result_directory>
#
# Supported packages
# ------------------
#   bitwarden  (default)  Desktop application built from source.
#   bw                    CLI prebuilt binary — no vendor tarballs needed.
#
# COPR passes spec=<path> (lowercase) via the "Spec File" field configured on
# the package.  The Makefile bridges this to SPEC (uppercase) below.
#
# The source generation phase HAS network access (for downloading sources
# and generating vendor tarballs).  The subsequent rpmbuild phase does NOT.
#
# IMPORTANT: The node vendor tarball (bitwarden only) is architecture-specific.
# COPR's Make SRPM runs once (typically on x86_64) and the resulting SRPM is
# used for all configured chroots.  If building for BOTH x86_64 and aarch64:
#   - Use COPR's "Custom" source method instead, OR
#   - Upload arch-specific SRPMs manually, OR
#   - Build only for the builder's native arch.
#
# See AGENTS.md for detailed multi-arch guidance.
# ============================================================================

# COPR invokes: make srpm outdir="..." spec="<spec_path>"  (lowercase spec=)
# Command-line override uses uppercase SPEC=.  Fall back to bitwarden.spec.
SPEC     ?= $(or $(spec),bitwarden.spec)
# SPECFILE is the basename of SPEC; COPR passes spec= as a full absolute path,
# so we must not concatenate it onto rpmbuild/SPECS/ directly.
SPECFILE := $(notdir $(SPEC))
VERSION  := $(shell rpmspec -q --queryformat '%{VERSION}\n' $(SPEC) 2>/dev/null | head -1)
NAME     := $(shell rpmspec -q --queryformat '%{NAME}\n' $(SPEC) 2>/dev/null | head -1)

# COPR passes outdir=<path>; default to current directory for local use
outdir ?= .

.PHONY: srpm
srpm:
	@echo "==> Building SRPM for $(NAME) $(VERSION)"

	# ---- Install base tools needed for source generation ----
	# The COPR source-generation environment is a minimal Fedora container.
	dnf install -y rpmdevtools curl

	# ---- Install bitwarden-specific build tools ----
	if [ "$(NAME)" = "bitwarden" ]; then \
	    dnf install -y nodejs npm rust cargo zstd; \
	fi

	# ---- Set up rpmbuild tree ----
	mkdir -p rpmbuild/{SOURCES,SPECS,BUILD,RPMS,SRPMS}

	# ---- Download upstream source(s) ----
	spectool -g -C rpmbuild/SOURCES $(SPEC)

	# ---- Bitwarden Desktop: generate vendor tarballs + copy aux files ----
	if [ "$(NAME)" = "bitwarden" ]; then \
	    ./generate-vendor-tarball.sh $(VERSION); \
	    mv bitwarden-$(VERSION)-node-vendor.tar.zst rpmbuild/SOURCES/; \
	    mv bitwarden-$(VERSION)-cargo-vendor.tar.zst rpmbuild/SOURCES/; \
	    cp com.bitwarden.desktop.desktop rpmbuild/SOURCES/; \
	    cp com.bitwarden.desktop.metainfo.xml rpmbuild/SOURCES/; \
	fi

	# ---- Copy spec ----
	cp $(SPEC) rpmbuild/SPECS/

	# ---- Build SRPM ----
	rpmbuild \
		--define "_topdir $(CURDIR)/rpmbuild" \
		-bs rpmbuild/SPECS/$(SPECFILE)

	# ---- Copy result to output directory ----
	cp rpmbuild/SRPMS/*.src.rpm $(outdir)/

	@echo "==> SRPM written to $(outdir)/"
