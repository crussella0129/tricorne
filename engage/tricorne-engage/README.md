<!--
SPDX-FileCopyrightText: 2026 Thread & Signal LLC
SPDX-License-Identifier: CC-BY-SA-4.0
-->

# tricorne-engage

**The Tricorne Purple Corner engagement workflow CLI.**

`tricorne-engage` is the single command that manages a pentest
engagement from kickoff to sealed evidence artifact. It is the layer
that makes offensive work legible to defensive review — the thing no
other offensive distribution ships.

## Status

**v0.1.0.dev0 — MVP scaffolding.** Commands exist, models exist,
three functions in `scope.py`, `log.py`, and `models.py` are left as
`TODO(charles):` blocks for Charles to implement. Tests are in place
to verify those implementations once written.

## Commands

| Command                            | What it does                                                |
|------------------------------------|-------------------------------------------------------------|
| `tricorne-engage new <client>`     | Creates `~/engagements/<client>/`, writes engagement log    |
| `tricorne-engage scope <file>`     | Loads a scope JSON into the active engagement               |
| `tricorne-engage scope`            | Prints the currently loaded scope                           |
| `tricorne-engage seal`             | Finalizes the engagement into a signed, hashed artifact     |

v0.1 MVP is deliberately these three. `log`, `capture`, and `report`
are v0.2.

## Engagement lifecycle

```
                                    ┌────────────────────────────┐
                                    │  tricorne-engage new X     │
                                    │  creates ~/engagements/X/  │
                                    └─────────────┬──────────────┘
                                                  │
                                                  ▼
                                    ┌────────────────────────────┐
                                    │  tricorne-engage scope F   │
                                    │  copies F into workspace,  │
                                    │  validates, logs load      │
                                    └─────────────┬──────────────┘
                                                  │
                          ┌───────── normal engagement work ──────────┐
                          │  tools check scope.json; every invocation │
                          │  appends a JSON Lines entry to the log;   │
                          │  hash chain accumulates.                  │
                          └─────────────┬─────────────────────────────┘
                                        │
                                        ▼
                                    ┌────────────────────────────┐
                                    │  tricorne-engage seal      │
                                    │  (see "Sealing", below)    │
                                    └────────────────────────────┘
```

## Filesystem layout

```
~/engagements/<client-slug>/
├── engagement.json         # metadata: slug, created_at, state
├── scope.json              # scope file (absent until `scope <f>` runs)
├── engagement.log          # JSON Lines, hash-chained, append-only
├── artifacts/              # tool output, screenshots, extracted data
└── .seal/                  # seal-in-progress marker (transient)

~/engagements-sealed/
└── <client-slug>-<date>-sealed.tar.gz   # read-only; SELinux tricorne_report_t
    └── (contains manifest.json + seal.sig + the engagement artifacts)

~/.local/state/tricorne/
├── engagement-index.jsonl  # external index outside any seal
└── active-engagement       # symlink to the current engagement, if any
```

## On-disk formats

All state on disk is **strict JSON** (no YAML, no TOML, no JSONC). This
is a deliberate choice 2026-04-24:

- AI tools read and write scope/logs at least as often as humans do;
  JSON parsing is ~10× faster and stdlib-only
- No ambiguous parsing (YAML's "Norway problem", TOML datetime edge cases)
- Every language has JSON in its standard library

JSON has no comments. To preserve the "why was this excluded?"
provenance that scope files need, annotations live in a structured
`notes` field on the scope model itself — timestamped, author-tagged,
referenced by scope-entry ID.

### Timestamps

Every timestamp field in Tricorne is an **`AwareDatetime`** — a
pydantic-v2 type that rejects naive datetimes at validation time. The
on-disk serialization is ISO 8601 with 4-digit year and explicit UTC
offset: `2026-04-25T09:00:00+00:00`. This matters for evidence
handling: a reviewer should never have to guess the zone or the
century of a timestamp. Months-without-year (`Apr 25 09:00` from
`ls`, `find`, or `ps`) are a shell-display artifact we never emit to
disk.

## The hash chain

The engagement log is JSON Lines: one JSON object per line,
append-only. Each line has a `prev_hash` field containing the hex
SHA-256 of the previous line's canonical bytes. The first line's
`prev_hash` is `"0" * 64`.

Example:

```jsonl
{"ts":"2026-04-25T09:00:00Z","actor":"operator","action":"engagement_new","mode":"live","payload":{"client":"acme"},"prev_hash":"0000000000000000000000000000000000000000000000000000000000000000"}
{"ts":"2026-04-25T09:01:15Z","actor":"operator","action":"scope_loaded","mode":"live","payload":{"scope_file":"scope.json","sha256":"abc..."},"prev_hash":"7b2c9..."}
{"ts":"2026-04-25T09:02:31Z","actor":"tool-wrapper:nmap","action":"scan_start","mode":"live","payload":{"target":"10.0.0.1","scope_decision":"IN"},"prev_hash":"91dd0..."}
```

A tamper anywhere in the chain — editing, inserting, or deleting a
line — changes every `prev_hash` after it. The Merkle root computed
over the final log state at seal time is GPG-signed, so the chain is
pinned to a moment in time.

## Sealing

`tricorne-engage seal` is the one-shot operation that converts a live
engagement workspace into a court-admissible evidence artifact. It
answers four questions a reviewer might ask:

- **Integrity**: is the artifact byte-identical to what existed at
  engagement close?
- **Provenance**: did this specific operator produce it, not someone
  after the fact?
- **Completeness**: was anything quietly deleted before sealing?
- **Time**: when did this happen, and can you prove no later edits?

### What sealing does, step by step

1. **Freeze.** A `SEAL_INITIATED` entry is appended to the engagement
   log. A `.seal/pid` lockfile is written. Further writes to the
   workspace will invalidate the seal; a second seal attempt is
   refused.
2. **Enumerate + hash.** Walk the workspace recursively. For every
   file, record `{path, size, mode, owner, selinux_context,
   sha256_hex}` in a `manifest.json`. The manifest lists exactly what
   existed at seal time.
3. **Build a Merkle tree.** Each file's SHA-256 is a leaf. Internal
   nodes are `SHA-256(left_hash || right_hash)`. The **Merkle root**
   is a single 32-byte hash that changes if *any* file's content
   changes. Same mechanism as Git tree objects.
4. **Close the hash chain.** Append a final `SEAL_MERKLE_ROOT` entry
   to the engagement log, carrying the Merkle root. The chain is now
   complete.
5. **Sign.** GPG-sign `(merkle_root || engagement_metadata ||
   final_log_hash)` with the operator's key. Output: `seal.sig` —
   a detached, ASCII-armored signature. **No signing key = no seal.**
   Signatures are the whole point of aggressive sealing; making them
   optional defeats the purpose.
6. **Archive.** `tar` the workspace + `manifest.json` + `seal.sig` into
   `<client>-<date>-sealed.tar.gz`. The tarball is moved into
   `~/engagements-sealed/`.
7. **Unmount LUKS.** The live workspace's LUKS volume is cleanly
   unmounted. (v0.1: this step is a TODO pending Fedora validation.)
8. **External index.** A single line is appended to
   `~/.local/state/tricorne/engagement-index.jsonl` recording
   timestamp, workspace, Merkle root, signature fingerprint. This
   survives even if the sealed tarball is later lost — it is proof
   that the seal *happened*, kept outside the sealed artifact.

### Verifying a sealed artifact

```bash
tricorne-engage verify acme-webapp-2026-sealed.tar.gz
```

(v0.2 command.) The verifier:

- Unpacks the tarball in a scratch directory
- Walks the files, recomputes every SHA-256, rebuilds the Merkle tree
- Compares the reconstructed Merkle root to the one in `seal.sig`
- Verifies the GPG signature against the operator's public key
- Replays the log hash chain from line 1 to the final
  `SEAL_MERKLE_ROOT` entry
- Reports `SEAL VALID` or names the first tampered element

## `--dev` mode

Tricorne's Purple Corner tooling is designed to run inside the
SELinux `tricorne_engagement_t` context. That context only exists on a
Tricorne (or otherwise compatible) Fedora system. Development
happens on Windows, macOS, and Linux-without-SELinux, so the tool
needs a mode that runs there without lying about the safety posture.

`--dev` is that mode, with five guards:

1. **Two-key activation.** Requires *both* `--dev` flag and
   `TRICORNE_DEV_MODE=1` environment variable. Accidental activation
   is a two-key failure, not one.
2. **Loud banner on every command.** A red `rich`-rendered panel
   prints on every invocation, not once per session.
3. **Mode is in every log entry.** Log entries include `mode:
   "dev"`, so dev activity is visible in the hash-chained record.
4. **Dev-touched workspaces cannot be sealed.** If any log entry in
   a workspace has `mode: "dev"`, `tricorne-engage seal` refuses with
   a clear error. Dev and live cannot mix inside a sealed artifact.
5. **No-op when SELinux already enforcing.** When
   `getenforce` reports `Enforcing` *and* the `tricorne_t` domain is
   loaded, `--dev` does nothing — the real checks fire at the
   kernel regardless of user-space flags.

This is materially equivalent to "refuse to run outside SELinux,
period" for live-engagement security posture, while preserving the
cross-platform dev loop. The insider-threat and accidental-dev risks
are both foreclosed by guard #4: you can't produce a verifiable
sealed artifact from a dev-tainted workspace.

## Install (dev)

```bash
# From the repo root:
python -m pip install -e 'engage/tricorne-engage[test]'

# Verify:
tricorne-engage --help
```

## Testing

```bash
cd engage/tricorne-engage
pytest
```

Tests in `tests/test_scope.py` and `tests/test_log.py` define the
contract for the three `TODO(charles):` functions. They will fail
with `NotImplementedError` until you implement them, then pass once
the implementations meet the contract.

## License

Apache-2.0. See the repo root `LICENSE`.
