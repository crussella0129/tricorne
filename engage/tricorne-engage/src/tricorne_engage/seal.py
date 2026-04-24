# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Sealing: convert a live workspace into a signed, hashed, read-only artifact.

The full conceptual explanation lives in
`engage/tricorne-engage/README.md` under "Sealing". This module is the
orchestration skeleton. Several steps require a real Fedora system to
validate (LUKS unmount, SELinux context setting); those are clearly
marked TODO_FEDORA and will be exercised the first time Charles runs
the full flow in a VM.

This module is intentionally NOT one of the `TODO(charles):` learning
slots — it is long, multi-step, and the right-vs-wrong decisions are
not where meaningful design input goes (those are in scope.py,
log.py, and models.py). Read it to understand the flow; it should
largely just work once the three TODOs are filled in.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from tricorne_engage import log as log_mod
from tricorne_engage import paths
from tricorne_engage.models import (
    GENESIS_HASH,
    Engagement,
    EngagementState,
    LogEntry,
    SealManifest,
    SealManifestFile,
)


class SealError(Exception):
    """Raised for any seal-time failure. The CLI catches and renders these."""


@dataclass(frozen=True)
class SealResult:
    """Return value from `seal()` — everything a reviewer needs for follow-up."""

    tarball_path: Path
    merkle_root_hex: str
    signature_fingerprint: str
    index_line_appended: bool


# ----------------------------------------------------------------------------
# Step 1 — freeze
# ----------------------------------------------------------------------------


def _check_not_dev_tainted(log_path: Path) -> None:
    """Refuse to seal a workspace that has any `mode: "dev"` entries.

    Parses each line as a LogEntry and inspects the typed `mode` field,
    rather than doing a byte-substring match on the serialized form. The
    on-disk serialization's whitespace and key order are not
    contractually stable across pydantic releases or future custom
    serializers; a substring check could silently false-negative after a
    dependency bump, or false-positive on an unrelated payload value
    that happens to contain the literal bytes. This is a security
    boundary — parse and check the type.

    An unparseable log line is itself evidence of corruption or tamper
    and causes seal to refuse: a sealed artifact whose audit trail has
    undeclared gaps is worse than no artifact at all.
    """
    if not log_path.exists():
        return
    with log_path.open("rb") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = LogEntry.model_validate_json(raw)
            except ValidationError as e:
                raise SealError(
                    f"log line {lineno} is unparseable; will not seal a "
                    f"workspace whose audit trail has been corrupted: {e}"
                ) from e
            if entry.mode == "dev":
                raise SealError(
                    f"workspace contains a dev-mode log entry at line {lineno}; "
                    "dev-tainted workspaces cannot be sealed. "
                    "See README '#--dev mode' guard #4."
                )


def _freeze(engagement: Engagement, log_path: Path) -> None:
    """Write the seal lockfile and the SEAL_INITIATED log entry."""
    lock = paths.seal_lock_path(engagement.client_slug)
    if lock.exists():
        raise SealError(
            f"seal lock already exists at {lock}. A previous seal crashed; "
            "resolve manually before proceeding."
        )
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()))

    log_mod.append(
        log_path,
        actor="operator",
        action="seal_initiated",
        payload={"seal_pid": os.getpid()},
    )


# ----------------------------------------------------------------------------
# Step 2 — enumerate + hash
# ----------------------------------------------------------------------------


def _sha256_file(path: Path, block_size: int = 1 << 20) -> str:
    """Streamed SHA-256 of a file. 1 MiB blocks avoid loading big PCAPs into RAM."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def _selinux_context_of(path: Path) -> str | None:
    """Return the SELinux context string for a path, or None if unsupported.

    On Tricorne Fedora, we'd read from /proc/self/attr/fs/<pid>/current
    or use libselinux. For v0.1 MVP, shell out to `stat --printf=%C`.
    On non-SELinux hosts this simply returns None.
    """
    try:
        result = subprocess.run(
            ["stat", "--printf=%C", str(path)],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if not out or out == "?":
        return None
    return out


def _enumerate_workspace(workspace: Path) -> list[SealManifestFile]:
    """Walk `workspace`, build a SealManifestFile for every regular file.

    Excludes .seal/ (the transient seal lockfile). Sorted by path so
    the manifest is deterministic — same workspace, same manifest.
    """
    files: list[SealManifestFile] = []
    for p in sorted(workspace.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(workspace)
        rel_str = rel.as_posix()
        if rel_str.startswith(".seal/"):
            continue
        stat = p.stat()
        files.append(
            SealManifestFile(
                path=rel_str,
                size=stat.st_size,
                mode=stat.st_mode & 0o7777,
                sha256_hex=_sha256_file(p),
                selinux_context=_selinux_context_of(p),
            )
        )
    return files


# ----------------------------------------------------------------------------
# Step 3 — Merkle tree
# ----------------------------------------------------------------------------


def _merkle_root(leaf_hexes: list[str]) -> str:
    """Compute the Merkle root over the given hex leaf hashes.

    Standard binary Merkle tree:
      - Leaves: each file's SHA-256 (32 bytes raw)
      - Internal node: SHA-256(left || right)
      - Odd count at any level: duplicate the last node

    Returns a hex string for easy embedding in JSON. An empty input
    returns the GENESIS_HASH sentinel so downstream validators always
    have a 64-char hex string to compare.
    """
    if not leaf_hexes:
        return GENESIS_HASH

    level = [bytes.fromhex(h) for h in leaf_hexes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            hashlib.sha256(level[i] + level[i + 1]).digest()
            for i in range(0, len(level), 2)
        ]
    return level[0].hex()


# ----------------------------------------------------------------------------
# Step 5 — sign
# ----------------------------------------------------------------------------


def _default_gpg_key() -> str | None:
    """Return the operator's default GPG signing key fingerprint, if any.

    Shells out to `gpg --list-secret-keys --with-colons`. The first
    secret key with capability "s" (sign) wins. Returns None if no
    secret keys are available — in which case seal refuses.
    """
    try:
        result = subprocess.run(
            ["gpg", "--list-secret-keys", "--with-colons"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    # --with-colons output: fpr lines contain the fingerprint at field 9.
    # We look for the first fpr following an sec line with sign capability.
    lines = result.stdout.splitlines()
    in_signing_sec = False
    for line in lines:
        parts = line.split(":")
        if not parts:
            continue
        if parts[0] == "sec":
            # field 11 is capabilities string ("sc", "scea", etc.)
            caps = parts[11] if len(parts) > 11 else ""
            in_signing_sec = "s" in caps
        elif parts[0] == "fpr" and in_signing_sec:
            if len(parts) > 9:
                return parts[9]
            in_signing_sec = False
    return None


def _gpg_sign_bytes(data: bytes, fingerprint: str) -> bytes:
    """Produce a detached ASCII-armored signature over `data`.

    Raises SealError if gpg is unavailable or the signature fails.
    """
    try:
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--armor",
                "--detach-sign",
                "--local-user", fingerprint,
                "--output", "-",
                "-",
            ],
            input=data,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        raise SealError(
            "gpg binary not found. Install gnupg2 (Fedora: `dnf install gnupg2`)."
        ) from None
    if result.returncode != 0:
        raise SealError(
            f"gpg signing failed (rc={result.returncode}): {result.stderr.decode('utf-8', 'replace')}"
        )
    return result.stdout


# ----------------------------------------------------------------------------
# Step 6 — archive
# ----------------------------------------------------------------------------


def _make_tarball(source: Path, dest: Path, extra_files: dict[str, bytes]) -> None:
    """Create `dest` (.tar.gz) from `source/` plus injected extra files.

    `extra_files` maps in-archive path -> content, for manifest.json
    and seal.sig which live alongside the workspace contents inside
    the tarball.

    Uses gzip for v0.1 — ubiquitous, stdlib, good-enough compression.
    v0.2 likely migrates to zstd.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tar:
        tar.add(source, arcname=source.name, recursive=True)
        for arcpath, content in extra_files.items():
            info = tarfile.TarInfo(name=f"{source.name}/{arcpath}")
            info.size = len(content)
            info.mtime = int(datetime.now(timezone.utc).timestamp())
            tar.addfile(info, io.BytesIO(content))


# ----------------------------------------------------------------------------
# Step 7 — unmount LUKS  (TODO_FEDORA)
# ----------------------------------------------------------------------------


def _unmount_engagement_luks(engagement: Engagement) -> None:
    """Unmount the LUKS volume that holds this engagement's workspace.

    TODO_FEDORA: implement when running on a Tricorne system. Needs
    `cryptsetup luksClose <mapping>` and an `umount` before it. The
    mapping name convention will be defined in v0.2 alongside the
    `tricorne-engage new` LUKS provisioning code.

    For v0.1 MVP on dev workstations, this is a no-op and the function
    returns cleanly. Log entry makes the no-op explicit.
    """
    # TODO_FEDORA: real implementation.
    return


# ----------------------------------------------------------------------------
# Step 8 — external index
# ----------------------------------------------------------------------------


def _append_to_engagement_index(
    engagement: Engagement,
    merkle_root_hex: str,
    tarball_path: Path,
    fingerprint: str,
) -> bool:
    """Append a single-line record to ~/.local/state/tricorne/engagement-index.jsonl.

    This file lives OUTSIDE any sealed artifact. It is proof that the
    seal happened, surviving even if the tarball is later lost.
    """
    index_path = paths.engagement_index_path()
    paths.ensure_state_dir()

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "slug": engagement.client_slug,
        "tarball_path": str(tarball_path),
        "merkle_root": merkle_root_hex,
        "gpg_fingerprint": fingerprint,
    }
    line = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
    with index_path.open("ab") as fh:
        fh.write(line)
        fh.write(b"\n")
        fh.flush()
        os.fsync(fh.fileno())
    return True


# ----------------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------------


def seal(engagement: Engagement) -> SealResult:
    """Seal a live engagement workspace into a signed, read-only artifact.

    High-level flow (see README.md "Sealing" for the full explanation):
      1. Refuse dev-tainted workspaces.
      2. Freeze (lockfile + SEAL_INITIATED log entry).
      3. Enumerate and hash all files into a manifest.
      4. Compute Merkle root over file hashes.
      5. Append SEAL_MERKLE_ROOT log entry (closes the hash chain).
      6. GPG-sign (merkle_root || engagement metadata || final_log_hash).
      7. Archive workspace + manifest + signature into a tarball.
      8. Unmount LUKS (no-op on dev hosts).
      9. Append external index line.

    Raises SealError with a useful message on any failure.
    """
    slug = engagement.client_slug
    workspace = paths.engagement_root(slug)
    log_path = paths.engagement_log_path(slug)

    _check_not_dev_tainted(log_path)
    _freeze(engagement, log_path)

    try:
        # 3 — enumerate + hash
        manifest_files = _enumerate_workspace(workspace)

        # 4 — Merkle root
        merkle_root_hex = _merkle_root([f.sha256_hex for f in manifest_files])

        # 5 — close the hash chain
        log_mod.append(
            log_path,
            actor="operator",
            action="seal_merkle_root",
            payload={"merkle_root": merkle_root_hex, "file_count": len(manifest_files)},
        )
        final_log_hash = log_mod.read_last_hash(log_path)

        # 6 — sign
        fingerprint = _default_gpg_key()
        if fingerprint is None:
            raise SealError(
                "no GPG signing key available. Aggressive sealing requires a signature. "
                "Generate a key with `gpg --full-generate-key` or configure your existing "
                "key as the default."
            )

        sealed_at = datetime.now(timezone.utc)
        manifest = SealManifest(
            engagement_slug=slug,
            sealed_at=sealed_at,
            files=manifest_files,
            merkle_root_hex=merkle_root_hex,
            final_log_hash_hex=final_log_hash,
            operator_gpg_fingerprint=fingerprint,
        )
        manifest_bytes = json.dumps(
            manifest.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        # The signed bytes explicitly cover (protocol version, slug,
        # sealed_at ISO 8601 with year+offset, merkle root, final log hash).
        # Including sealed_at here — rather than relying solely on the
        # manifest or GPG's own sig-creation-time — means a reviewer
        # verifying the signature can assert WHEN the seal happened from
        # the signed bytes themselves, not only from ancillary metadata.
        sealed_at_iso = sealed_at.isoformat()  # always 'YYYY-MM-DDTHH:MM:SS+00:00'
        to_sign = b"|".join([
            b"TRICORNE-SEAL-v1",
            slug.encode("utf-8"),
            sealed_at_iso.encode("ascii"),
            merkle_root_hex.encode("ascii"),
            final_log_hash.encode("ascii"),
        ])
        signature_bytes = _gpg_sign_bytes(to_sign, fingerprint)

        # 7 — archive
        tarball = paths.sealed_dir() / f"{slug}-{sealed_at.strftime('%Y%m%d-%H%M%S')}-sealed.tar.gz"
        _make_tarball(
            source=workspace,
            dest=tarball,
            extra_files={
                "manifest.json": manifest_bytes,
                "seal.sig": signature_bytes,
            },
        )

        # 8 — unmount LUKS (no-op on dev)
        _unmount_engagement_luks(engagement)

        # 9 — external index
        appended = _append_to_engagement_index(engagement, merkle_root_hex, tarball, fingerprint)

        return SealResult(
            tarball_path=tarball,
            merkle_root_hex=merkle_root_hex,
            signature_fingerprint=fingerprint,
            index_line_appended=appended,
        )

    finally:
        # Always clear the seal lock. A crash mid-seal leaves partial state,
        # but the lockfile removal lets the operator retry after fixing.
        lock = paths.seal_lock_path(slug)
        if lock.exists():
            try:
                lock.unlink()
                lock.parent.rmdir()  # remove .seal/ if empty
            except OSError:
                pass  # best-effort cleanup
