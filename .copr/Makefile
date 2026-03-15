# ============================================================================
# COPR Make SRPM — generates the source RPM for Bitwarden Desktop.
#
# COPR's "Make SRPM" SCM method clones this git repo on a builder and runs:
#   make -f .copr/Makefile srpm outdir=<result_directory>
#
# The source generation phase HAS network access (for downloading sources
# and generating vendor tarballs).  The subsequent rpmbuild phase does NOT.
#
# IMPORTANT: The node vendor tarball is architecture-specific.  COPR's
# Make SRPM runs once (typically on x86_64) and the resulting SRPM is used
# for all configured chroots.  If building for BOTH x86_64 and aarch64:
#   - Use COPR's "Custom" source method instead, OR
#   - Upload arch-specific SRPMs manually, OR
#   - Build only for the builder's native arch.
#
# See AGENTS.md for detailed multi-arch guidance.
# ============================================================================

SPEC    := bitwarden.spec
VERSION := $(shell rpmspec -q --queryformat '%{VERSION}\n' $(SPEC) 2>/dev/null | head -1)

# COPR passes outdir=<path>; default to current directory for local use
outdir ?= .

.PHONY: srpm
srpm:
	@echo "==> Building SRPM for Bitwarden Desktop $(VERSION)"

	# ---- Install tools needed for source generation ----
	# The COPR source-generation environment is a minimal Fedora container.
	# These packages are NOT available by default.
	dnf install -y nodejs npm rust cargo rpmdevtools zstd curl

	# ---- Set up rpmbuild tree ----
	mkdir -p rpmbuild/{SOURCES,SPECS,BUILD,RPMS,SRPMS}

	# ---- Download upstream source + Electron binaries ----
	spectool -g -C rpmbuild/SOURCES $(SPEC)

	# ---- Generate vendor tarballs (requires network) ----
	./generate-vendor-tarball.sh $(VERSION)
	mv bitwarden-$(VERSION)-node-vendor.tar.zst rpmbuild/SOURCES/
	mv bitwarden-$(VERSION)-cargo-vendor.tar.zst rpmbuild/SOURCES/

	# ---- Copy auxiliary source files ----
	cp bitwarden.sh rpmbuild/SOURCES/
	cp com.bitwarden.desktop.desktop rpmbuild/SOURCES/
	cp com.bitwarden.desktop.metainfo.xml rpmbuild/SOURCES/

	# ---- Copy spec ----
	cp $(SPEC) rpmbuild/SPECS/

	# ---- Build SRPM ----
	rpmbuild \
		--define "_topdir $(CURDIR)/rpmbuild" \
		-bs rpmbuild/SPECS/$(SPEC)

	# ---- Copy result to output directory ----
	cp rpmbuild/SRPMS/*.src.rpm $(outdir)/

	@echo "==> SRPM written to $(outdir)/"
