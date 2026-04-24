<!--
SPDX-FileCopyrightText: 2026 Thread & Signal LLC
SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Tricorne — Design Specification

*Status: Design Spec v0.3 — Pre-implementation*
*Author: Charles Russella (Thread & Signal LLC)*
*Target: Unofficial Fedora Remix → Official Fedora Spin (2–3 year roadmap)*

> *"My treasure? If you want it, I'll let you have it. Seek it out! I left everything at that place!"*
> — Gol D. Roger, Pirate King

This file is the architectural source of truth for Tricorne. Where this document and any other conflicts, **DESIGN.md wins**. See `CLAUDE.md` §1.

---

## 1. Thesis

Kali owns Debian. BlackArch owns Arch. Parrot owns the "security-focused desktop" niche. **No one owns RPM-world offensive security**, despite Fedora being arguably the most defensively hardened mainstream distro — SELinux, sVirt, OpenSCAP, and the audit framework all originated in Red Hat/NSA collaboration.

Tricorne fills that gap. It is a Fedora Remix that ships the offensive security toolchain (network recon, web app testing, wireless, exploitation frameworks, forensics, reverse engineering) on top of Fedora's defensive foundation, with first-class SELinux policy support for every tool in the catalog.

The name comes from the three-cornered hat worn by irregular forces, militia, and privateers from roughly 1690 to 1800 — the asymmetric-warfare hat. The tricorne wasn't designed for parade formations; it was a practical modification soldiers made themselves, pinning up the brim of a wide hat so it wouldn't catch on musket slings and shoulder gear. **A hat redesigned by operators for operators.** That's the Linux distro origin story in physical form.

The three corners are the design metaphor: **red team, blue team, purple team — three aspects of one operator's practice, in one system.**

- **Red corner:** offensive tooling (Port Horn of the old Bicorne spec, now expanded)
- **Blue corner:** SELinux, audit framework, hardening defaults
- **Purple corner:** engagement workspaces, scope enforcement, logging, reporting — the unifying layer that makes red-team work legible to blue-team review

Kali, BlackArch, and Parrot all address only the red corner. Tricorne is the first major offensive distro to treat all three as first-class.

The differentiating bet: **red teamers who operate in SELinux-enforcing environments (federal, DoD, regulated industries) currently have no native distro, and the purple-team discipline is growing without a dedicated platform.** Tricorne serves both at once.

## 2. Non-Goals

Clarity on what Tricorne is *not* prevents scope creep.

- **Not a Kali clone.** Same toolset, different base, different philosophy. We don't replicate Kali's metapackage structure 1:1.
- **Not a hardening distro.** Qubes, Tails, and Whonix occupy that space. Tricorne is offensive tooling on Fedora's defaults.
- **Not a rolling release.** We inherit Fedora's ~6-month cadence. Pentest tools that need bleeding-edge versions ship via Flatpak or toolbx containers.
- **Not beginner-oriented.** We assume dnf, SELinux basics, and Linux fluency. Training wheels live in Kali.
- **Not a forensics-first distro.** CAINE and SIFT own that. We include forensics tools but don't optimize the UX around them.

## 3. Primary Users (concentric rings)

**Ring 0 — Core wedge:** Red teamers and pentesters at government contractors, federal agencies, and regulated industries (healthcare, finance, defense) where target environments run RHEL/Rocky/Alma with SELinux enforcing. Currently underserved.

**Ring 1:** Purple team practitioners building the feedback loop between offensive and defensive operations. Currently cobbling together toolchains across multiple distros.

**Ring 2:** Pentesters frustrated with Debian's packaging lag for fast-moving tools (modern C2 frameworks, post-quantum crypto tooling, LLM-adjacent exploitation).

**Ring 3:** Students in offensive security programs who want to learn in a hardened environment rather than an intentionally permissive one.

**Ring 4:** Existing Fedora users who want pentest tools without distro-hopping.

The distro serves all five, but design trade-offs resolve in favor of Rings 0 and 1.

## 4. Architecture

### 4.1 Base

- **Fedora Workstation** (current stable, N-1 supported) as the upstream base
- **GNOME** as the reference desktop (Fedora's default; we don't fight upstream)
- **Secondary spins:** KDE, Hyprland (for the tiling-WM crowd that dominates offensive sec culture)
- **No kernel forks.** We ship stock Fedora kernel. If a tool needs kernel modules, it ships them as DKMS or kmod packages.

### 4.2 The Three Corners

The metaphor carries through to the technical architecture. Tricorne is organized around three corners:

**Red Corner — Offensive:**
The pentest toolchain. Recon, exploitation, post-exploitation, C2. Lives primarily in `tricorne-*` metapackages (web, wireless, ad, etc.). Every tool here has a counterpart policy in the Blue Corner.

**Blue Corner — Defensive:**
SELinux policies (`tricorne_t` domain and friends), audit rule sets, hardening defaults, threat model documentation. Not optional, not disabled. Every Red Corner tool ships with its Blue Corner counterpart: a tested SELinux policy module, audit rules, and a documented threat model for running that tool on an operator's workstation.

**Purple Corner — Unifying:**
Engagement workspaces, scope enforcement, automatic logging, evidence capture, report generation. This is the layer that makes offensive work legible to defensive review — and it's the layer no other offensive distro ships. Lives in the `tricorne-engage` toolkit (see §7.2).

Three-tier packaging model underneath:

**Tier 1 — Native RPM packages** in the `tricorne` COPR/repo. Core tools that benefit from system integration: `nmap`, `wireshark`, `metasploit-framework`, `aircrack-ng`, `hashcat`, `john`, `hydra`, `sqlmap`, `burpsuite-community`, `zaproxy`, `radare2`, `ghidra`, `gdb-peda`, `volatility3`, `bettercap`, `responder`. Packaged with proper SELinux policies (see §5).

**Tier 2 — Flatpak** for GUI tools that churn fast or have complex dependency trees. Keeps them isolated and updatable independently of Fedora's release cycle.

**Tier 3 — Toolbx containers** for tools that are genuinely hostile to SELinux or need specific library versions. `tricorne-toolbx-kali` provides a Kali environment via containerized Debian for tools we can't or won't native-package.

### 4.3 Metapackages

Modeled loosely on Kali's metapackage structure, but RPM-native and organized by corner:

```
# Red Corner (offensive toolchain)
tricorne-everything      # kitchen sink
tricorne-default         # reasonable daily-driver subset
tricorne-web             # web app testing
tricorne-wireless        # 802.11, Bluetooth, SDR
tricorne-network         # recon, MITM, pivoting
tricorne-exploitation    # frameworks, payload generation
tricorne-forensics       # memory, disk, network forensics
tricorne-reversing       # RE and malware analysis
tricorne-crypto          # hash cracking, crypto analysis
tricorne-osint           # passive recon
tricorne-cloud           # AWS/Azure/GCP red team tooling
tricorne-ad              # Active Directory / Kerberos
tricorne-mobile          # Android/iOS testing

# Blue Corner (defensive / policy)
tricorne-selinux-policy  # all tricorne_* SELinux modules
tricorne-audit-rules     # auditd rules tuned for operator workstation
tricorne-hardening       # additional CIS-aligned defaults

# Purple Corner (unifying)
tricorne-engage          # engagement workspace toolkit
tricorne-report          # evidence collection, report templates
```

### 4.4 Filesystem Layout

Follow Fedora conventions strictly. No `/opt/tricorne` dumping ground. Tools install to standard locations (`/usr/bin`, `/usr/share`, `/usr/lib`). Wordlists, payloads, and shared assets live under `/usr/share/tricorne/` with symlinks for Kali-compatibility (`/usr/share/wordlists`, `/usr/share/seclists`) so muscle memory from Kali transfers.

## 5. Blue Corner: SELinux

This is the section that justifies Tricorne's existence. Every other offensive distro treats SELinux as an obstacle. We treat it as a feature.

### 5.1 Default Posture

- SELinux runs **enforcing** by default. Not permissive. Not disabled.
- Every Tier 1 tool ships with a tested, upstream-submitted SELinux policy module.
- Tools that genuinely require policy exceptions (e.g., raw socket access for `nmap` SYN scans, promiscuous mode for `wireshark`) get **narrow, documented booleans** rather than blanket `setenforce 0` workarounds.

### 5.2 The `tricorne_t` Domain Family

A set of new SELinux domains for offensive security workflows:

- `tricorne_t` — tools launched via `tricorne-shell` or graphical session entry points transition here. Elevated capabilities for packet crafting, raw sockets, and process introspection — but still constrained from reading `/etc/shadow`, arbitrary home directories, or system config
- `tricorne_target_t` — scratch directories where exploit development happens, isolated from user data
- `tricorne_engagement_t` — active engagement workspaces (see §7.2), with additional audit hooks
- `tricorne_report_t` — evidence and report artifacts, read-only to operator tools once sealed

This is the thing gov/defense red teamers will pay attention to. When their client's SOC sees a Tricorne workstation on the network, the audit trail is *better* than a Kali box, not worse.

### 5.3 Policy Module Submission

Every Tier 1 tool's SELinux policy gets submitted upstream to `selinux-policy` where applicable. Tricorne becomes a **net contributor** to Fedora's security posture, not a taker. This is critical for the eventual Fedora Spin application — the Fedora Council will care that we're upstream-friendly.

## 6. Red Corner: Toolchain Catalog (v0.1 Draft)

Partial list. Full catalog lives in `CATALOG.md`. Every entry includes: upstream URL, Fedora packaging status, SELinux policy status, metapackage membership, tier.

### 6.1 Network Recon & Enumeration
- `nmap`, `masscan`, `rustscan`, `naabu` (ProjectDiscovery suite)
- `amass`, `subfinder`, `assetfinder`
- `dnsrecon`, `dnsenum`, `fierce`

### 6.2 Web Application
- `burpsuite-community`, `zaproxy`, `caido`
- `ffuf`, `gobuster`, `feroxbuster`, `dirsearch`
- `sqlmap`, `nosqlmap`, `commix`
- `nuclei`, `nikto`, `wapiti`

### 6.3 Wireless & SDR
- `aircrack-ng` suite, `bettercap`, `kismet`, `wifite`
- `hcxtools`, `hcxdumptool`
- `gnuradio`, `gqrx`, `hackrf`, `rtl-sdr` tooling
- Bluetooth: `bluez` tooling, `btlejack`

### 6.4 Exploitation Frameworks
- `metasploit-framework` (native RPM, not bundled Ruby mess)
- `sliver`, `havoc`, `mythic` (modern C2 — via Flatpak or toolbx)
- `empire`, `covenant`
- `exploitdb` / `searchsploit`

### 6.5 Active Directory & Windows
- `impacket` suite, `bloodhound`, `bloodhound-python`
- `crackmapexec` / `netexec`, `kerbrute`, `rubeus` (via dotnet)
- `responder`, `mitm6`, `ntlmrelayx`

### 6.6 Password & Cryptography
- `hashcat` (with proper GPU driver handling), `john`
- `hydra`, `medusa`, `patator`
- `cewl`, wordlist management tooling
- `seclists` integration

### 6.7 Reverse Engineering
- `ghidra`, `radare2`, `rizin`, `cutter`
- `gdb` with `pwndbg`, `gef`, `peda` (user-selectable)
- `binwalk`, `firmware-mod-kit`
- `frida`, `objection`

### 6.8 Forensics & IR (defensive crossover)
- `volatility3`, `autopsy`, `sleuthkit`
- `yara`, `loki`
- `chainsaw`, `hayabusa` (Windows event log analysis)

### 6.9 OSINT
- `spiderfoot`, `maltego-ce`, `recon-ng`
- `theharvester`, `photon`, `sherlock`

### 6.10 Cloud & Container
- `pacu`, `scout-suite`, `prowler`
- `kube-hunter`, `kubeaudit`, `peirates`
- `trufflehog`, `gitleaks`

## 7. Purple Corner: User Experience

### 7.1 First Boot
- Live ISO boots to a minimal GNOME with "Tricorne Setup" as a featured app
- Setup wizard offers metapackage selection, VPN preconfig, engagement workspace creation
- Clear disclaimer about legal use — not a EULA wall, but a conscious opt-in

### 7.2 Engagement Workspaces
The Purple Corner's headline feature. **Engagement workspaces** are LUKS-encrypted directories under `~/engagements/<client>/` with their own SELinux context (`tricorne_engagement_t`), automatic screenshot/logging capture (toggleable), and scope-file parsing that warns if `nmap` is about to scan an out-of-scope IP.

Commands:
- `tricorne-engage new <client>` — creates encrypted workspace, drops you into it
- `tricorne-engage scope <file>` — loads scope file; subsequent tool invocations respect it
- `tricorne-engage log <message>` — append a timestamped note to the engagement log
- `tricorne-engage capture` — manual evidence capture (screenshot + active terminal dump)
- `tricorne-engage seal` — closes workspace, unmounts LUKS volume, generates engagement log
- `tricorne-engage report` — hands off sealed workspace to `tricorne-report` for draft generation

Scope file format: simple YAML with in-scope and out-of-scope CIDR blocks, URLs, and time windows. Tools that support scope enforcement (`nmap`, `masscan`, `ffuf`, `nuclei`) get thin wrappers that check the active scope file before executing. Out-of-scope targets produce a loud refusal with a `--force-out-of-scope` override that gets logged.

This is a feature Kali lacks entirely and that working pentesters — especially those who've ever been on the wrong side of a scope mistake — would immediately use.

### 7.3 Branding & Theming

**The purple tricorne is the entire brand thesis compressed into an image.** Every other offensive security distro uses a dark/red/"hacker" aesthetic that codes red-team-only. A purple hat transmits immediately, before any copy, that Tricorne fuses red, blue, and purple disciplines. The color *is* the positioning.

- **Logo:** Stylized tricorne silhouette in three-quarter profile (not pure side view — three-quarter shows all three corners distinctly and is unambiguously a tricorne at small sizes). Hat body in deep violet. A firebrick red cockade (the revolutionary-era rosette) pinned to the upturned brim, preserving the offensive identity and preventing the logo from reading as purely defensive. Ships as SVG, scales from favicon to billboard.
- **Wordmark:** "Tricorne" set in a clean sans-serif with slightly condensed letterforms. Reads "tactical" not "edgy."
- **Two official lockups from day one:**
  - *Icon mark* — tricorne silhouette with cockade, square composition, for favicons and app icons
  - *Horizontal wordmark* — icon plus "Tricorne" wordmark, for website headers, READMEs, and presentations
- **Color palette:**
  - Primary: Deep violet `#4B0082` (indigo) — regal, authoritative, historically the color of ink and strategy
  - Accent: Cockade red `#B22222` (firebrick) — the offensive heritage, unmissable
  - Highlight: Cream `#F5F1E8` — parchment/map-chart callback, softens the digital feel
  - Detail: Matte black `#0A0A0A` — outlines, wordmark, supporting UI chrome
- Dark theme default. No skull-and-crossbones. The hat is the whole aesthetic — strategist, not pirate.
- Icon set: custom Tricorne branding, ships as part of `tricorne-artwork`.

**Differentiation from Kali Purple:** Kali Purple is Kali's *defensive* spin, launched 2023. Tricorne is a whole distro covering the full red/blue/purple discipline — purple in the Tricorne brand means "the unified operator," not "defensive only." In docs and marketing: *"Kali Purple is Kali's defensive spin. Tricorne is the whole discipline — red, blue, and purple as three corners of one hat."* Kali Purple's existence is evidence of market demand for the purple-team frame, not a competing claim on it.

### 7.4 Shell
- `zsh` with a curated Tricorne prompt (engagement name, target IP when set, SELinux context)
- `tmux` config preinstalled with pane logging enabled (auditability by default)
- `bash` fully supported; `fish` as optional
- Default prompt symbol: a small Unicode tricorne glyph where available, fallback to `⚔` or `>`

## 8. Infrastructure

### 8.1 Repo Hosting
- **COPR** initially (`@tricorne/default`, `@tricorne/web`, etc.) — free Fedora-native infrastructure, no capex
- Migrate to dedicated infra once traffic justifies it
- GPG-signed repos from day one, no exceptions

### 8.2 Build System
- Koji-compatible builds via COPR
- GitHub Actions for ISO builds (`livemedia-creator` / `kickstart` based)
- All kickstart files and artwork in the main repo

### 8.3 Source of Truth
- Monorepo at `github.com/crussella0129/tricorne` (or org account `github.com/tricorne-project`)
- Subtrees for: `packaging/` (RPM specs), `selinux/` (policy modules), `kickstart/` (ISO definitions), `artwork/`, `docs/`, `metapackages/`, `engage/` (Purple Corner tooling)

### 8.4 CI/CD
- Every PR triggers: RPM build, SELinux policy compile, rpmlint, ISO smoke test in QEMU
- Weekly automated ISO builds for nightly/rawhide track
- Release ISOs tagged quarterly, aligned with Fedora releases

## 9. Roadmap

### v0.1 — Proof of Concept (Months 0–3)
- COPR repo live with 20–30 Tier 1 tools packaged
- `tricorne-default` metapackage working
- One SELinux policy module submitted upstream (target: `nmap`)
- Working kickstart that produces a bootable ISO
- README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.md in place
- Logo and wordmark finalized

### v0.2 — Usable Remix (Months 3–9)
- 80% of the catalog packaged across the three tiers
- `tricorne_t` domain policy working end-to-end
- Engagement workspace feature shipping (Purple Corner MVP)
- 5+ contributors beyond you
- First public release announcement (r/netsec, r/linux, r/fedora, Hacker News)

### v0.3 — Remix Maturity (Months 9–18)
- Full catalog, all metapackages functional
- Flatpak runtime published
- Kali-compat toolbx image published
- Documentation site at `tricorne-linux.org` (or similar)
- Purple Corner reporting pipeline (draft report generation from engagement logs)
- Conference presence: DEF CON demo, BSides talks
- First corporate user (consultancy standardizing on it)

### v1.0 — Official Fedora Spin Application (Months 18–36)
- Fedora Spin proposal submitted to FESCo
- Working Group formed with 3+ maintainers
- All packages reviewed and in Fedora proper (not just COPR)
- Official branding approval from Fedora Council
- First ISO shipped as Fedora Tricorne Spin

## 10. Risks & Open Questions

**Trademark search.** "Tricorne" appears in fashion/retail (hat makers, costume suppliers), a font foundry, and a few small businesses. Nothing in software or security that creates confusion. USPTO search in classes 9 (software) and 42 (software services) and domain availability check needed before public launch.

**Metasploit packaging.** Metasploit's Ruby dependency graph is an RPM nightmare. Kali special-cases it. We'd need to either special-case it, ship it as a Flatpak, or push upstream to clean up their gemspec.

**Ghidra & Java.** Fedora's Java packaging is tightly scoped. Ghidra works but is finicky. Ship as Flatpak is probably correct.

**Kernel module conflicts.** Some wireless tools need specific driver patches (e.g., injection-capable `rtl8812au` drivers). DKMS handles this but breaks on kernel updates. Needs a tested update path.

**Scope enforcement bypass.** The Purple Corner scope wrappers add friction — operators will want an override. The override must be logged, but it cannot be so frictionful that operators just disable the wrapper entirely. Getting this UX right is a real design problem.

**Community overlap.** Parrot Security OS exists and has some Fedora-curious users. Reach out early; don't duplicate effort if a collaboration is possible.

**Fedora Council acceptance.** Official spin status requires demonstrating that Tricorne doesn't damage Fedora's reputation. Security tools cut both ways — need to be proactive about ethics/legal framing.

## 11. Governance

- **BDFL model initially** (Charles Russella / Thread & Signal LLC). Clarity beats democracy at v0.
- Transition to working group model by v0.3 once there are 3+ committed maintainers.
- Code of Conduct: Fedora's, verbatim.
- **Licensing (multi-license by artifact type):**
  - Packaging files (RPM specs, kickstarts, build scripts): **MIT**
  - Original code (Purple Corner tooling): **Apache-2.0** (for patent grant)
  - SELinux policy modules: **GPL-2.0-or-later** (matches upstream `selinux-policy`, required for upstream submission)
  - Artwork, logos, icons: **CC BY-SA 4.0** with trademark carve-out (Tricorne name and marks remain trademarks of Thread & Signal LLC — see `TRADEMARK.md`)
  - Documentation: **CC BY-SA 4.0**
  - Upstream packaged tools keep their own upstream licenses
- **All source files carry SPDX headers** for machine-readable license identification. Required by modern Fedora packaging guidelines.
- **Contributions use DCO, not CLA.** Contributors sign off commits with `git commit -s`, certifying the Developer Certificate of Origin. Matches Fedora's model; no contribution friction.
- **No GPL-3.0 or AGPL-3.0 for original code.** Creates legal-review friction with the Ring 0 gov/defense audience. Apache-2.0 is the right license for this wedge.

## 12. How to Contribute (v0.1 stub)

Stub section. Full `CONTRIBUTING.md` is the authoritative guide.

Immediate asks:
- RPM spec reviewers (Fedora packagers who know the drill)
- SELinux policy reviewers (rare skill, high value)
- Tool maintainers willing to own a specific subcatalog
- Purple Corner contributors — Python/Rust developers interested in engagement tooling
- ISO testers with varied hardware

---

## Appendix A — Comparison Matrix

| Feature | Kali | BlackArch | Parrot | Tricorne |
|---------|------|-----------|--------|----------|
| Base | Debian | Arch | Debian | Fedora |
| Release model | Rolling-ish | Rolling | Rolling | 6-month |
| SELinux | Disabled | Disabled | AppArmor | **Enforcing** |
| Tool count | ~600 | ~2800 | ~600 | Target: 400–600 curated |
| Container story | Weak | None | Weak | **Native (toolbx)** |
| Immutable variant | No | No | No | **Planned (Silverblue base)** |
| Engagement workspaces | No | No | No | **Yes (Purple Corner)** |
| Scope enforcement | No | No | No | **Yes** |
| Evidence/report pipeline | No | No | No | **Yes** |
| Gov/defense ready | No | No | No | **Primary wedge** |

## Appendix B — Etymology & Brand Story

The tricorne (from Latin *tricornis*, "three-horned") emerged in the late 17th century as a practical soldier's modification, not a fashion statement. Wide-brimmed hats worn by European infantry kept catching on musket slings, cartridge boxes, and shoulder-fired gear. Soldiers started pinning up the brim on three sides to keep it out of the way — a bottom-up hack that became standard issue across most European armies by the 1690s and persisted through the American Revolution.

It was the hat of the Continental Army, the Minutemen, colonial militia, and — not coincidentally — pirates and privateers. Asymmetric forces operating against larger, better-equipped, more traditional adversaries. The hat of people who had to out-think rather than out-spend their opposition.

The design lesson transfers directly: **the tools that win asymmetric engagements are the ones the operators shape themselves to fit the work.** Tricorne the distro inherits that principle. It integrates with Fedora's defaults rather than replacing them; it runs inside SELinux rather than disabling it; it fits the operator's existing environment rather than demanding a dedicated VM.

The three corners are the operator's three disciplines: attack, defend, account. Red, blue, purple. One hat, one head, one operator.

*Three corners. One operator.*
