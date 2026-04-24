<!--
SPDX-FileCopyrightText: 2026 Thread & Signal LLC
SPDX-License-Identifier: CC-BY-SA-4.0
-->

<p align="center">
  <!-- artwork/logo-horizontal.svg — coming with v0.1 branding pass -->
  <em>[logo placeholder — deep-violet tricorne with firebrick cockade; see <code>artwork/</code>]</em>
</p>

<h1 align="center">Tricorne</h1>
<p align="center"><strong>A Fedora Remix for offensive security.</strong></p>
<p align="center"><em>"My treasure? If you want it, I'll let you have it. Seek it out! I left everything at that place!" Gol D. Roger</em></p>

<p align="center">
  <img alt="status" src="https://img.shields.io/badge/status-pre--v0.1-orange">
  <img alt="license" src="https://img.shields.io/badge/license-multi--license-informational">
  <img alt="SELinux" src="https://img.shields.io/badge/SELinux-enforcing-success">
</p>

---

> *"My treasure? If you want it, I'll let you have it. Seek it out! I left everything at that place!"*
> — Gol D. Roger

## The short version

Kali owns Debian. BlackArch owns Arch. Parrot owns the "security-focused desktop" niche. **No one owns RPM-world offensive security** — even though Fedora is arguably the most defensively hardened mainstream distribution. Tricorne fills that gap.

It ships the offensive security toolchain (recon, web, wireless, exploitation, forensics, RE) on top of Fedora's defaults — **SELinux enforcing, audit framework on, sVirt active** — and adds an engagement-workflow layer that no other offensive distribution ships.

## Three corners

- **Red Corner — Offensive toolchain.** Pentest tools packaged as RPM (Tier 1), Flatpak (Tier 2), or toolbx containers (Tier 3). Matches Kali's content scope; packaged the Fedora way.
- **Blue Corner — Defensive foundation.** SELinux policy modules for every Tier 1 tool. Audit rules tuned for operator workstations. Hardening defaults. Not optional, not disabled.
- **Purple Corner — Unifying workflow.** LUKS-encrypted engagement workspaces, scope-file enforcement that warns before out-of-scope scans, evidence capture, and draft-report generation. The layer that makes offensive work legible to defensive review.

## Status

**Pre-v0.1.** The design spec is frozen (see [`DESIGN.md`](DESIGN.md)); scaffolding and initial packaging are underway.

Current v0.1 priorities (from [`CLAUDE.md`](CLAUDE.md) §6):
1. First RPM packaged (`nmap` as the pattern template)
2. `tricorne_t` SELinux domain (base policy module)
3. Minimal bootable ISO (kickstart)
4. Purple Corner MVP (`tricorne-engage new`, `scope`, `seal`)
5. COPR repo live, launch docs shipped
6. One SELinux policy module submitted upstream

Follow the [issues](https://github.com/crussella0129/tricorne/issues) for the authoritative backlog.

## Quickstart

> Once v0.1 ships. The commands below are the *intended* interface, not yet functional.

```bash
# Add the Tricorne COPR
sudo dnf copr enable @tricorne/default

# Install a metapackage
sudo dnf install tricorne-default     # reasonable daily-driver subset
# or
sudo dnf install tricorne-everything  # kitchen sink

# Start an engagement
tricorne-engage new acme-webapp-2026
tricorne-engage scope scope.yaml
# ... work happens, automatically logged ...
tricorne-engage seal
```

Until v0.1 ships, there is nothing to install. Watch or star the repo.

## Documentation

| File | What it is |
|------|-----------|
| [`DESIGN.md`](DESIGN.md) | Architecture spec. Source of truth for design decisions. |
| [`CLAUDE.md`](CLAUDE.md) | Instructions for AI coding assistants. Human contributors should read it too — the golden rules apply to everyone. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute: DCO sign-off, licensing by artifact type, CI expectations, workflow guides. |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Fedora's Code of Conduct, adopted verbatim. |
| [`SECURITY.md`](SECURITY.md) | Vulnerability disclosure policy for Tricorne itself. |
| [`TRADEMARK.md`](TRADEMARK.md) | Name and logo usage policy. |
| [`LICENSE`](LICENSE) | Multi-license summary. Full texts in [`LICENSES/`](LICENSES/). |

## License

Tricorne is a multi-license project. At a glance: **MIT** for packaging, **Apache-2.0** for original code, **GPL-2.0-or-later** for SELinux policy, **CC-BY-SA-4.0** for artwork and documentation. Upstream tools keep their upstream licenses. See [`LICENSE`](LICENSE) for the full table.

## Trademarks

"Tricorne" and the Tricorne logo marks are trademarks of Thread & Signal LLC. See [`TRADEMARK.md`](TRADEMARK.md) for what you can do without asking and what requires permission.

---

<p align="center"><em>Three corners. One operator.</em></p>
