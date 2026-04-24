<!--
SPDX-FileCopyrightText: 2026 Thread & Signal LLC
SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Contributing to Tricorne

Tricorne welcomes contributions from packagers, SELinux policy authors,
Python/Rust developers, documentation writers, and security practitioners.
This file tells you how to contribute productively. If something here is
unclear or wrong, open an issue.

## Before you start

- Read [`README.md`](README.md) for the elevator pitch.
- Read [`DESIGN.md`](DESIGN.md) for the architecture.
- Read [`CLAUDE.md`](CLAUDE.md) if you intend to use an AI coding assistant
  on this repo. Its rules apply to human contributors too — the project's
  golden rules are shared across both.
- Scan the [open issues](https://github.com/crussella0129/tricorne/issues).
  We use GitHub issues as the authoritative backlog.

## What we accept

- **RPM specs** for security tools with legitimate upstreams. See
  `DESIGN.md` §6 for the catalog scope.
- **SELinux policy modules**. This is rare and high-leverage work.
- **Purple Corner tooling** under `engage/`. Python first, Rust where
  justified.
- **Documentation, translations, typo fixes**. Always welcome.
- **Bug reports, reproduction cases, SELinux AVC logs from real tool runs**.

## What we don't accept

Per `CLAUDE.md` §3.4 and §5:

- **Original exploits, 0days, custom payloads.** Vulnerabilities found
  against upstream tools go through coordinated disclosure to those
  upstreams, not into this repo.
- **Real credentials, API keys, client data, engagement artifacts, or
  captured traffic from real networks.** Use placeholders like
  `TEST_CREDENTIAL_DO_NOT_USE`. Public CTF corpora are acceptable if you
  cite them.
- **Scripts, CI jobs, or docs that run `setenforce 0` or disable SELinux.**
  Not even temporarily. Not even "just for testing."
- **Tools forked into this repo instead of packaged from upstream.**
  Tricorne is a packaging project. If a tool's license or upstream is
  unhealthy, flag it for Charles to decide, don't fork-and-merge.

## How to contribute

### 1. Open or claim an issue first

For anything non-trivial, open an issue or comment on an existing one
before writing code. This prevents duplicate work and lets a maintainer
redirect you if the approach has a known problem.

### 2. Fork, branch, develop

1. Fork `github.com/crussella0129/tricorne` to your account.
2. Branch from `main`: `git checkout -b your-topic`.
3. Make your changes. See the workflow-specific guides below for
   packaging, policy, and Purple Corner work.

### 3. Sign off every commit (DCO)

Tricorne uses the [Developer Certificate of Origin](https://developercertificate.org/).
Every commit must include a `Signed-off-by:` line. The easiest way:

```bash
git commit -s -m "your message"
```

This adds the line from your `user.name` and `user.email`.

By signing off you certify that you have the right to submit the contribution
under the project's licensing terms. There is no separate CLA; no legal
document to sign. This matches Fedora's contribution model.

### 4. Add SPDX headers

Every source file we ship carries a two-line SPDX header. Match the license
to the artifact class (see `LICENSE`).

```text
# SPDX-FileCopyrightText: 2026 Your Name <you@example.com>
# SPDX-License-Identifier: Apache-2.0
```

For Markdown, YAML, and other files where `#` is not the comment syntax:

```text
<!--
SPDX-FileCopyrightText: 2026 Your Name <you@example.com>
SPDX-License-Identifier: CC-BY-SA-4.0
-->
```

Run `reuse lint` locally to verify coverage.

### 5. Keep CI green

Every PR runs:

- `rpmbuild` in mock for affected packages
- `checkmodule` + `semodule_package` for affected SELinux policies
- `rpmlint` on all touched spec files
- `pytest` / `cargo test` for affected Purple Corner code
- `reuse lint` for SPDX coverage
- ISO smoke test in QEMU (release branches only)

Red CI does not merge. Do not "just rerun" flaky tests without
investigating the underlying cause.

### 6. Open a PR

PR descriptions must include:

- **What** — one-sentence summary.
- **Why** — the problem being solved or capability being added.
- **Test plan** — how you verified the change. For packaging:
  `rpmbuild` output, `rpmlint` output. For policy: `ausearch -m avc`
  showing no unexpected denials. For code: new/modified tests and
  passing-run evidence.
- **Upstream links** — for packaging, link to the upstream project
  and to any existing Fedora packaging effort.

Commit messages: imperative mood, subject ≤72 characters, body explains
*why*, not *what*. GPG-sign where possible.

## Workflow-specific guides

### Packaging a new tool (Red Corner)

See `CLAUDE.md` §4.2. In brief:

1. Check Fedora first: `dnf search <tool>`, `src.fedoraproject.org`. If
   the tool is already in Fedora, **do not repackage** — depend on it. The
   appropriate Tricorne contribution in that case is a wrapper package
   (`tricorne-<tool>`) that installs our SELinux policy module and sets
   any needed booleans. See `packaging/nmap/` for the canonical example.
2. Create `packaging/<tool>/` with a `<tool>.spec`, a `README.md`
   explaining rationale and maintainer, and a `sources/` subdirectory.
3. Build in mock: `fedpkg --release f<N> mockbuild`.
4. Write or adapt the SELinux module in `selinux/<tool>/`.
5. `rpmlint` and `fedora-review`; fix every error and warning.
6. Add the package to the appropriate metapackage.
7. Open a PR.

### Writing a SELinux policy module (Blue Corner)

See `CLAUDE.md` §4.3. In brief:

- Start from an existing similar module in
  `/usr/share/selinux/devel/include/`.
- Use `audit2allow` only as a first draft. Every generated rule gets
  reviewed and justified.
- Prefer existing interfaces. If you must define a new one, put it in
  `<module>.if` with full documentation.
- Never grant `sys_admin`, `dac_override`, or `setuid` without explicit
  justification in the module README.
- Boolean-gate any capability that a locked-down deployment might
  reasonably want to disable.

### Purple Corner tooling

See `CLAUDE.md` §4.4. Language preference order:

1. **Python** for CLI tools, scope parsers, report generators. `typer`
   for CLI, `pydantic` for data models, `rich` for output.
2. **Rust** for anything that needs to be fast, long-running, or touch
   the filesystem aggressively. `clap` for CLI, `serde` for
   serialization, `tokio` for async.
3. **Shell** only for glue scripts under ~30 lines. Longer shell scripts
   get rewritten in Python.

All Purple Corner tooling must:

- Refuse to run outside a `tricorne_engagement_t` context (or warn
  loudly in `--dev` mode).
- Log every action to the engagement log in structured JSON.
- Fail closed on scope violations. Override flags must be explicit
  (`--force-out-of-scope`) and always logged.

## Code of Conduct

Tricorne adopts the Fedora Project's Code of Conduct verbatim. See
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Licensing your contribution

Your contribution is licensed under the license applicable to the file(s)
you modify, per the table in [`LICENSE`](LICENSE). If you are creating a
new file, match the license to the directory you are adding it to:

- `packaging/`, `kickstart/`, `metapackages/`, CI configs → **MIT**
- `engage/`, other original code → **Apache-2.0**
- `selinux/` → **GPL-2.0-or-later**
- `artwork/`, `docs/`, all `*.md` → **CC-BY-SA-4.0**

We do not accept **GPL-3.0** or **AGPL-3.0** contributions for original
code (`engage/`). See `DESIGN.md` §11 for rationale (gov/defense
legal-review friction).

## Questions

- General questions: open a [GitHub Discussion](https://github.com/crussella0129/tricorne/discussions).
- Security-sensitive matters: see [`SECURITY.md`](SECURITY.md).
- Anything else: open an issue. Maintainers will respond.

Thanks for contributing.

*Three corners. One operator.*
