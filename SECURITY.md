<!--
SPDX-FileCopyrightText: 2026 Thread & Signal LLC
SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Security Policy

Tricorne is a security project. We take vulnerability reports seriously and
commit to responding quickly. This document covers how to report
vulnerabilities **in Tricorne itself** — our RPM specs, SELinux policy
modules, kickstart files, Purple Corner tooling, and documentation.

If you have found a vulnerability in an upstream packaged tool (nmap,
Metasploit, etc.), report it to that upstream project, not to us. Tricorne
does not maintain fixes to upstream tools; we package them.

## Scope

**In scope:**
- `engage/` — Purple Corner tooling (`tricorne-engage`, `tricorne-report`,
  scope parsers)
- `selinux/` — SELinux policy modules we author
- `packaging/` — RPM specs, patches, systemd units, scriptlets we author
- `kickstart/` — ISO build definitions
- `metapackages/` — metapackage specs
- `.github/workflows/` — CI configurations
- Documentation that prescribes security-sensitive behavior (scope
  enforcement, evidence handling, sealing semantics)

**Out of scope:**
- Vulnerabilities in upstream packaged tools. Report those to the tool's
  upstream.
- Vulnerabilities in Fedora, the Linux kernel, or other upstream
  dependencies. Report to
  [Fedora Security](https://fedoraproject.org/wiki/Security).
- General objections that "offensive security tools are dangerous."
  These are legitimate pentest tools with legitimate users. Use GitHub
  Discussions for policy debate.

## How to report

**Email:** `security@thread-and-signal.com`

**PGP key:** available at
`https://thread-and-signal.com/pgp/security.asc` (coming with v0.1
launch). Until that key exists, email with `[TRICORNE SECURITY]` in the
subject and we will arrange an encrypted channel.

**Please include:**

- A description of the vulnerability.
- Affected component (path in the repo, or specific RPM name).
- A reproduction case. For SELinux policy issues, include the AVC from
  `ausearch -m avc -ts recent`.
- Your assessment of severity and impact.
- Whether you want credit, and how (name, handle, organization).

**Please do not:**

- File a public GitHub issue for a security vulnerability.
- Disclose the vulnerability publicly before we have had a chance to
  respond.

## What we will do

- **Acknowledge** your report within 3 business days.
- **Triage** within 7 business days and respond with severity
  assessment and expected timeline.
- **Fix** or mitigate per severity (see below).
- **Credit** you in release notes unless you request otherwise.
- **Coordinate** public disclosure with you once a fix is ready.

## Severity and response timelines

These are targets, not contractual commitments. Real constraints (a
critical bug in a module shared with upstream; a reporter who wants to
disclose at a conference) can shift them.

| Severity       | Response target                                      |
|----------------|------------------------------------------------------|
| Critical       | Fix released within 7 days                           |
| High           | Fix released within 30 days                          |
| Medium         | Fix released within 90 days                          |
| Low            | Fix released in the next scheduled release           |
| Informational  | Triaged and documented; may not produce a code change |

Severity is assessed on: **what an attacker can do** (escalation, data
access, policy bypass), **preconditions** (local access, physical
access, specific engagement state), and **reach** (how many operators
are affected).

## Policy bypass reports (special handling)

SELinux policy bypass reports are high-value and will be triaged at
high priority. If you find a path that transitions out of `tricorne_t`
in a way we did not intend, or a set of booleans that combined produce
an unsafe state, please report it even if you are not sure it is
exploitable — we would rather harden early than ship permissive.

## Coordinated disclosure

Tricorne's default is **90-day coordinated disclosure**. If you need a
different window (conference timing, regulatory reporting), tell us up
front and we will negotiate in good faith.

## Safe harbor

We will not pursue legal action against researchers who:

- Make a good-faith effort to avoid privacy violations, destruction of
  data, or interruption of service.
- Report vulnerabilities in accordance with this policy.
- Do not publicly disclose before a coordinated window.
- Do not access, modify, or retain data beyond what is necessary to
  demonstrate the vulnerability.

This is not a bug bounty. We do not pay for vulnerability reports. We
do give public credit and, where we can, a direct thank-you to your
employer or university.

## Pre-v0.1 note

Tricorne is currently pre-v0.1. Infrastructure (PGP keys, a `security@`
email, DNS records) is being established. If any part of this policy
does not yet work end-to-end, email `crussella0129@gmail.com` with
`[TRICORNE SECURITY]` in the subject and we will route from there.
