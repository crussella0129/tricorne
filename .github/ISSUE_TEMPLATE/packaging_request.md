---
name: Packaging request
about: Request that a security tool be added to Tricorne
title: "[packaging] "
labels: packaging, needs-triage
assignees: ''
---

<!--
SPDX-FileCopyrightText: 2026 Thread & Signal LLC
SPDX-License-Identifier: CC-BY-SA-4.0
-->

<!--
  Before filing: check CATALOG.md (coming with v0.2) and open issues
  for an existing request. Also run `dnf search <tool>` — if it's
  already in Fedora, we may just need a wrapper package for SELinux
  integration rather than a full packaging effort.
-->

## Tool

- **Name:**
- **Upstream URL:**
- **License:** (check against Fedora's allowed licenses list)
- **Language / runtime:** (C, Go, Rust, Python, Ruby, Java, ...)

## Why add it

<!-- What does this tool do? Who uses it? Which engagement phase
     (recon, exploitation, post-ex, AD, forensics)? Is it already
     in Kali? -->

## Corner / metapackage membership

Which metapackage(s) should this belong to? (See `DESIGN.md` §4.3.)

- [ ] `tricorne-web`
- [ ] `tricorne-wireless`
- [ ] `tricorne-network`
- [ ] `tricorne-exploitation`
- [ ] `tricorne-forensics`
- [ ] `tricorne-reversing`
- [ ] `tricorne-crypto`
- [ ] `tricorne-osint`
- [ ] `tricorne-cloud`
- [ ] `tricorne-ad`
- [ ] `tricorne-mobile`
- [ ] `tricorne-everything` only

## Current Fedora status

- [ ] Already in Fedora proper (`dnf search`, `src.fedoraproject.org`)
- [ ] In a Fedora COPR somewhere else (paste URL)
- [ ] Not packaged anywhere for Fedora
- [ ] In Kali / Debian but not RPM-world

## Tier

Which tier does this tool belong in? (See `DESIGN.md` §4.2.)

- [ ] Tier 1 (native RPM) — tool benefits from system integration / SELinux policy
- [ ] Tier 2 (Flatpak) — GUI tool, fast-moving, or complex deps
- [ ] Tier 3 (toolbx) — SELinux-hostile or needs specific lib versions

## SELinux considerations

<!-- Does this tool need raw sockets? Promiscuous mode? ptrace?
     Anything unusual that would require a custom SELinux module
     beyond tricorne_t? -->

## Are you willing to maintain it?

- [ ] Yes, I can write and maintain the spec
- [ ] Yes, I can help review
- [ ] No, just requesting

## Additional context
