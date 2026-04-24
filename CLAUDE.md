# CLAUDE.md — Tricorne Project Instructions for Claude Code

This file tells Claude Code how to work on the Tricorne repository. Read this in full before making any changes.

---

## 1. Project Identity

**Tricorne** is a Fedora Remix for offensive security. It is not a Kali clone, it is not a hardening distro, and it is not a rolling release. It is organized around three corners:

- **Red Corner** — offensive toolchain (pentest tools packaged as RPM/Flatpak/toolbx)
- **Blue Corner** — SELinux policies, audit rules, hardening defaults
- **Purple Corner** — engagement workspaces, scope enforcement, evidence pipeline

The full design spec is in `DESIGN.md`. **Read `DESIGN.md` before making any architectural decision.** If something in this file conflicts with `DESIGN.md`, `DESIGN.md` wins and this file needs an update.

The project owner is Charles Russella (GitHub: `crussella0129`). BDFL governance through v0.3.

## 2. Repository Layout

```
tricorne/
├── DESIGN.md                    # The spec. Source of truth for architecture.
├── CLAUDE.md                    # This file.
├── README.md                    # Public-facing intro.
├── CONTRIBUTING.md              # Human contributor guide.
├── CODE_OF_CONDUCT.md           # Fedora's CoC, verbatim.
├── SECURITY.md                  # Vuln disclosure policy.
├── LICENSE                      # MIT for packaging/artwork, Apache-2.0 for original code.
├── packaging/                   # RPM specs. One directory per package.
│   └── <tool>/
│       ├── <tool>.spec
│       ├── sources/
│       └── README.md            # Why this tool is packaged, upstream URL, maintainer
├── selinux/                     # SELinux policy modules.
│   └── <module>/
│       ├── <module>.te          # Type enforcement
│       ├── <module>.fc          # File contexts
│       ├── <module>.if          # Interfaces
│       └── README.md            # Threat model for this policy
├── metapackages/                # RPM specs for tricorne-* metapackages.
├── kickstart/                   # ISO build definitions.
│   ├── tricorne-default.ks
│   ├── tricorne-everything.ks
│   └── spins/                   # KDE, Hyprland, etc.
├── engage/                      # Purple Corner tooling (Python preferred, Rust welcome).
│   ├── tricorne-engage/         # Main engagement CLI
│   ├── tricorne-report/         # Report generation
│   └── scope-parsers/           # Scope file parsers for wrapped tools
├── artwork/                     # Logos, wallpapers, icon sets.
├── docs/                        # User-facing documentation (mkdocs).
└── .github/
    ├── workflows/               # CI: rpmbuild, policy compile, ISO smoke test
    └── ISSUE_TEMPLATE/
```

If you need to create a directory not listed here, document it in a commit message and update this section.

## 3. Golden Rules

These are non-negotiable. Violating any of them should make you stop and ask.

### 3.1 Upstream First, Always

- Before packaging a tool, check if it's already in Fedora proper (`dnf search`, `src.fedoraproject.org`). If it is, don't repackage — depend on it.
- Before writing a SELinux policy module, check upstream `selinux-policy`. If a module exists, improve it upstream rather than shadowing it.
- Bug fixes to upstream tools go upstream. We are not a patchset maintainer.
- The goal is for Tricorne to eventually vanish into Fedora. Every piece that lands upstream is a success.

### 3.2 SELinux Stays Enforcing

- `setenforce 0` appears nowhere in this repository except in documentation explaining why we do not do it.
- Tools that require policy exceptions get **narrow booleans**, not domain-wide permissive.
- Every Tier 1 RPM must ship with or depend on a working SELinux policy. No exceptions.
- When in doubt, run `ausearch -m avc -ts recent` and design around the actual denials.

### 3.3 Fedora Conventions Strictly

- RPMs follow Fedora Packaging Guidelines. Run `rpmlint` and `fedora-review` before submitting a spec.
- No `/opt/tricorne`. Tools install to standard FHS locations.
- Systemd units where daemons are involved. No init scripts.
- Python packages follow Fedora's Python packaging guidelines.
- Rust packages use `cargo-rpm` and vendor dependencies per Fedora policy.

### 3.4 Scope: What Belongs in This Repo

Tricorne is a **packaging project**, period. We package upstream security tools for Fedora. That includes tools that ship payloads, exploits, shellcode, and webshells — because that's what pentest tools are. We match Kali's scope on content, not undercut it. A Tricorne box should have everything a Kali box has and then some.

**Aggressively package, including payload-bearing tools:**
- Metasploit Framework with its full module tree (payloads, exploits, encoders, NOPs, post modules)
- ExploitDB / searchsploit — the full local mirror
- MSFvenom / MSFPC payload generators
- SecLists, PayloadsAllTheTheThings, webshells collections
- Veil, Shellter, Unicorn, other payload obfuscation tools
- SET (Social Engineer Toolkit), BeEF, Empire, Sliver, Havoc, Mythic
- Impacket suite, CrackMapExec/NetExec, Responder, Mitm6, Ntlmrelayx
- Anything else that has a legitimate upstream and is used by working pentesters

These tools arrive through spec files that pull from the upstream tarball. The payloads are the tool's content, maintained upstream, with clear provenance. We do not filter, curate, or trim them.

**The one line we don't cross — original exploit authoring:**
- No `packaging/tricorne-custom-payloads/`, no `engage/my-cve-poc/`, no "here's a 0day we found"
- If a Tricorne contributor discovers a vulnerability, it goes through normal coordinated disclosure to the upstream project, not into this repo
- Tricorne-authored tooling is infrastructure (engagement workspaces, scope parsers, report generators, policy modules), not exploits

This matches Kali's scope exactly. Kali packages MSF and ExploitDB; Kali does not author original exploits. Their own authored content is workflow/integration (NetHunter, Undercover, Purple, metapackages). Tricorne's authored content is analogous: Purple Corner tooling, SELinux policy modules, engagement UX, metapackages, artwork.

**Data hygiene rules:**
- No real credentials, ever, even in test data. Use documented placeholders like `TEST_CREDENTIAL_DO_NOT_USE`.
- No engagement artifacts, client data, or captured traffic from real networks. `.gitignore` excludes `*.pcap`, `*.hccapx`, `*.potfile`, `*.ntds`, `engagements/`, and anything that could contain client data.
- If a test needs realistic data, use public CTF corpora or data Charles explicitly marks as safe to commit.

The test for any new content: "Would this also appear in Kali?" If yes and it comes from a legitimate upstream, package it. If it's authored by us and isn't an exploit, ship it. If it's authored by us and *is* an exploit, reject it — send it upstream.

### 3.5 Licensing Discipline

Tricorne is a multi-license project because a distro is a bundle of different kinds of artifacts. Follow the correct license for each kind:

- **Packaging files** (RPM specs, kickstarts, build scripts, CI configs): **MIT**
- **Original code** (Purple Corner tooling — `tricorne-engage`, `tricorne-report`, scope parsers, anything in `engage/`): **Apache-2.0** (for the patent grant)
- **SELinux policy modules**: **GPL-2.0-or-later** (matches upstream `selinux-policy`, required for upstream submission)
- **Artwork, logos, icons, wallpapers**: **CC BY-SA 4.0** with trademark carve-out (see `TRADEMARK.md`)
- **Documentation**: **CC BY-SA 4.0**
- **Upstream packaged tools**: keep their existing upstream licenses — the spec file is MIT but the software it packages keeps whatever license upstream uses. These are different things.

**SPDX headers required on every source file Claude Code authors or meaningfully modifies.** Format:

```
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Thread & Signal LLC
```

Fedora packaging guidelines now require SPDX identifiers, so doing this from day one prevents a massive refactor later.

**Check upstream licenses before packaging.** If a tool's license is ambiguous, proprietary-with-restrictions, or non-free by DFSG/Fedora standards, flag it and do not package until Charles resolves the question.

**Never pick GPL-3.0 or AGPL-3.0 for original code.** Gov contractors and defense integrators (Ring 0 audience) have explicit legal-review friction with these licenses. Apache-2.0 sails through every corporate legal review. Don't pick a fight with the wedge audience over licensing.

**Contributions use DCO, not CLA.** Contributors sign off commits with `git commit -s`, certifying the Developer Certificate of Origin. No legal document to sign. This matches Fedora's model and creates no contribution friction. CONTRIBUTING.md must spell this out.

### 3.6 Charles's Preferences

- Charles is learning Python and Rust actively. Prefer clear, commented code over clever one-liners.
- When introducing a library, explain why in the commit message or code comment — what it does, why it beats the stdlib alternative.
- Teach the logic, not just the syntax. Comments should explain *why*, not *what*.
- Don't skip steps "for convenience." If a task has five steps, do five steps. Charles types commands manually to understand them.
- Charles is a professional in Fusion 360 parametric CAD and Excel formula architecture. Treat adjacent engineering domains as peer-level. Do not over-explain CAD, mechanical design, or spreadsheet logic.
- Charles is not yet independently proficient in production Python/Rust. When writing non-trivial code, explain the architecture in prose before or alongside the code.

## 4. How to Work in This Repo

### 4.1 Before Starting Any Task

1. Read `DESIGN.md` if you haven't this session.
2. Check the GitHub issues for related work.
3. If the task touches packaging, check Fedora's existing packages first.
4. If the task touches SELinux, `ls /usr/share/selinux/devel/include/` to see what interfaces exist before writing new ones.
5. State your plan in chat before executing. Charles will approve or redirect.

### 4.2 Packaging a New Tool (Red Corner)

Workflow:

```
1. Verify the tool is not already in Fedora:
   dnf search <tool>
   curl -s "https://src.fedoraproject.org/api/0/projects?pattern=<tool>"

2. Create packaging/<tool>/ with:
   - <tool>.spec (start from an existing similar package)
   - README.md (upstream URL, maintainer, rationale for inclusion)

3. Build locally in a mock chroot:
   fedpkg --release f<N> mockbuild

4. Write or adapt a SELinux policy module in selinux/<tool>/.
   - Start with targeted policy
   - Test with the tool in enforcing mode, collect AVCs, iterate
   - Document the threat model in selinux/<tool>/README.md

5. Run rpmlint and fedora-review; fix all errors and warnings.

6. Add the package to the appropriate metapackage in metapackages/.

7. Open a PR. CI will build, compile policy, and run an ISO smoke test.
```

### 4.3 Writing a SELinux Policy Module (Blue Corner)

- Start from an existing similar module in `/usr/share/selinux/devel/include/`.
- Use `audit2allow` only as a first draft — every generated rule must be reviewed and justified.
- Prefer existing interfaces over new ones. If you must define a new interface, put it in `<module>.if` with full documentation.
- Never grant `sys_admin`, `dac_override`, or `setuid` without explicit justification in the module README.
- Boolean-gate any capability that might reasonably be disabled in a locked-down deployment.

### 4.4 Purple Corner Tooling

The `engage/` tree is where original code lives. Language preferences, in order:

1. **Python** for CLI tools, scope parsers, report generators. Use `click` or `typer` for CLI, `pydantic` for data models, `rich` for output.
2. **Rust** for anything that needs to be fast, long-running, or touch the filesystem aggressively. Use `clap` for CLI, `serde` for serialization, `tokio` for async.
3. **Shell** only for glue scripts under ~30 lines. Longer shell scripts get rewritten in Python.

All Purple Corner tooling must:
- Refuse to run outside a `tricorne_engagement_t` context (or warn loudly in `--dev` mode).
- Log every action to the engagement log in structured JSON.
- Fail closed on scope violations. Override flags must be explicit (`--force-out-of-scope`) and always logged.

### 4.5 Commits and PRs

- Commit messages: imperative mood, subject line ≤72 chars, body explains why.
- Every commit should build. No "WIP" commits in `main`; squash before merge.
- PR descriptions must include: what, why, test plan, and any upstream links.
- Sign commits with GPG where possible. This is a security project; provenance matters.

### 4.6 CI Expectations

Every PR runs:
- `rpmbuild` in mock for affected packages
- `checkmodule` + `semodule_package` for affected SELinux policies
- `rpmlint` on all spec files
- `pytest` / `cargo test` for Purple Corner code
- ISO smoke test in QEMU (boot to login, verify metapackage install)

If CI is red, the PR does not merge. Fix or revert. Do not "just rerun" flaky tests without investigating.

## 5. What NOT To Do

Claude Code should stop and ask Charles before:

- Adding a new top-level directory
- Changing the metapackage taxonomy in §4.3 of `DESIGN.md`
- Introducing a kernel patch or kernel module dependency
- Disabling any SELinux policy, even temporarily
- Adding a dependency on an AUR-equivalent or third-party repo outside Fedora/RPMFusion/COPR
- Packaging anything from a source whose license is unclear
- Touching `artwork/` logos (Charles is handling branding direction personally)
- Changing governance or licensing terms
- Posting anything to external sites (Reddit, Hacker News, Fedora mailing lists) on behalf of the project

Claude Code should NEVER:

- Commit real credentials, API keys, client data, or engagement artifacts
- Run `setenforce 0` in any script, CI job, or documentation example
- Add exploits, payloads, or shellcode to the repo
- Fork an upstream tool into this repo instead of packaging it
- Write code that silently downgrades security defaults

## 6. Current Priorities (v0.1)

In execution order:

1. **Domain and GitHub org registration** — Charles handles, not Claude Code
2. **`packaging/nmap/`** — first tool, establishes the packaging pattern
3. **`selinux/tricorne-base/`** — defines `tricorne_t` domain and core interfaces
4. **`kickstart/tricorne-default.ks`** — minimal bootable ISO
5. **COPR repo setup** — Charles handles the COPR side; Claude Code prepares spec files
6. **`engage/tricorne-engage/` MVP** — `new`, `scope`, `seal` commands only for v0.1
7. **`README.md`, `CONTRIBUTING.md`, `SECURITY.md`** — ship with v0.1 public launch
8. **One SELinux policy module submitted to upstream `selinux-policy`** — the credibility anchor

Each item has or will have a GitHub issue. Work on issues, not on impulse.

## 7. Working With Charles

- Charles operates best as an architect and systems thinker. When given a task, he often wants to understand the *shape* of the solution before the implementation. Lead with architecture, then code.
- Charles is time-constrained (young child at home, financial pressure). Be efficient with his attention. Lead with the answer. Show code without excessive preamble.
- When Charles asks "how does this apply to what I'm building?" — answer directly and concretely. Generic explanations waste his time.
- Charles values being told when he's wrong. Don't sugar-coat. If a design choice has a real problem, say so plainly and propose an alternative.
- Charles has a pattern he's named himself: "architect without enough builder reps." When possible, bias toward shipping small working things over specifying large unbuilt things. Push for code that runs.
- If asked to make a choice between two options, make the choice and justify it. Don't pass the decision back unless it genuinely requires Charles's judgment.

## 8. Reference Documents

- `DESIGN.md` — architecture spec, source of truth
- `CATALOG.md` — full tool catalog (to be created at v0.2)
- Fedora Packaging Guidelines: https://docs.fedoraproject.org/en-US/packaging-guidelines/
- SELinux Policy Writing Guide: https://selinuxproject.org/page/PolicyLanguage
- Fedora Spin Process: https://docs.fedoraproject.org/en-US/fesco/Changes_Policy/

When upstream docs conflict with this file, upstream wins. Update this file to match.

---

*Three corners. One operator.*
