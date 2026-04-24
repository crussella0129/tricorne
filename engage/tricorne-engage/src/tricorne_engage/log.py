# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Engagement log: append-only JSON Lines with a hash chain.

The chain is the tamper-evidence mechanism: each entry's `prev_hash`
commits to the canonical bytes of the entry before it. Editing,
inserting, or deleting a line anywhere invalidates every `prev_hash`
after it. The final log hash gets rolled into the seal manifest,
pinning the chain to a signed moment in time.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from tricorne_engage.models import GENESIS_HASH, LogEntry


def _sha256_hex(data: bytes) -> str:
    """Hex-encoded SHA-256 digest of `data`. Pinned here so every hash-using
    call site (log chain, manifest files, Merkle leaves) routes through one
    function — future migration to a different algorithm is a single-file change.
    """
    return hashlib.sha256(data).hexdigest()


def read_last_hash(log_path: Path) -> str:
    """Return the hash to use as `prev_hash` for the next entry.

    For a non-existent or empty log, return GENESIS_HASH. Otherwise,
    read the last non-empty line of the log, parse the LogEntry from
    it, and return SHA-256(that_entry.canonical_bytes()).

    Uses a seek-from-end strategy for large logs rather than reading
    the whole file. We only need the last line.
    """
    if not log_path.exists() or log_path.stat().st_size == 0:
        return GENESIS_HASH

    # Walk backward from EOF to the last newline. For typical log sizes
    # this reads one block; for abnormally long lines (> 8 KB) we
    # double the read and try again until we find a newline.
    chunk = 8192
    with log_path.open("rb") as fh:
        fh.seek(0, 2)  # end
        filesize = fh.tell()
        offset = max(0, filesize - chunk)
        while True:
            fh.seek(offset)
            data = fh.read(filesize - offset)
            # Strip one trailing newline if present so we don't split on it.
            if data.endswith(b"\n"):
                data = data[:-1]
            if b"\n" in data or offset == 0:
                last_line = data.rsplit(b"\n", 1)[-1]
                break
            chunk *= 2
            offset = max(0, filesize - chunk)

    if not last_line.strip():
        return GENESIS_HASH

    entry = LogEntry.model_validate_json(last_line)
    return _sha256_hex(entry.canonical_bytes())


def append(
    log_path: Path,
    *,
    actor: str,
    action: str,
    payload: dict,
    mode: str = "live",
    ts: datetime | None = None,
) -> LogEntry:
    """Append a new entry to the engagement log.

    Automatically computes `prev_hash` from the last entry (or
    GENESIS_HASH for a fresh log) and writes the new line. Returns the
    constructed LogEntry for the caller that may want its hash.

    Flush is fsync'd: evidence logs that don't hit disk are worse than
    useless, and the performance cost (a few ms per write) is
    acceptable for engagement-rate traffic.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    prev_hash = read_last_hash(log_path)
    entry = LogEntry(
        ts=ts or datetime.now(timezone.utc),
        actor=actor,
        action=action,
        mode=mode,  # type: ignore[arg-type]
        payload=payload,
        prev_hash=prev_hash,
    )

    # Single-line JSON, no trailing newline inside the value; we add \n.
    line = entry.model_dump_json().encode("utf-8")
    with log_path.open("ab") as fh:
        fh.write(line)
        fh.write(b"\n")
        fh.flush()
        os.fsync(fh.fileno())

    return entry


def verify_chain(log_path: Path) -> tuple[bool, str]:
    """Replay the chain and confirm every prev_hash is correct.

    Returns (ok, reason). On failure, `reason` names the first line at
    which the chain breaks. This is the primary verification routine
    called by `tricorne-engage verify` (v0.2) and by `seal` before
    finalizing.
    """
    if not log_path.exists():
        return True, "empty log"

    prev = GENESIS_HASH
    with log_path.open("rb") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            entry = LogEntry.model_validate_json(raw)
            if entry.prev_hash != prev:
                return (
                    False,
                    f"line {lineno}: prev_hash does not match computed hash "
                    f"of line {lineno - 1}",
                )
            prev = _sha256_hex(entry.canonical_bytes())
    return True, "ok"
