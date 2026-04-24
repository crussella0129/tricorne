# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Contract tests for log.py and models.py::LogEntry.canonical_bytes.

Most of these fail with NotImplementedError until Charles fills in
the TODO in models.py::LogEntry.canonical_bytes. Once that function
is implemented, the rest of the log machinery (append, verify_chain)
starts working.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from tricorne_engage import log as log_mod
from tricorne_engage.models import GENESIS_HASH, LogEntry


def _entry(**overrides) -> LogEntry:
    defaults = dict(
        ts=datetime(2026, 4, 25, 9, 0, 0, tzinfo=timezone.utc),
        actor="operator",
        action="scan_start",
        mode="live",
        payload={"target": "10.0.0.1"},
        prev_hash=GENESIS_HASH,
    )
    defaults.update(overrides)
    return LogEntry(**defaults)


# ---------------------------------------------------------------------------
# canonical_bytes contract
# ---------------------------------------------------------------------------

def test_canonical_bytes_is_bytes():
    """The return type is bytes, not str. Hashing consumes bytes."""
    e = _entry()
    assert isinstance(e.canonical_bytes(), bytes)


def test_canonical_bytes_same_data_same_bytes():
    """Two entries built from equal field values produce equal bytes.

    This is the invariant that makes the hash chain reproducible.
    """
    e1 = _entry(payload={"a": 1, "b": 2})
    e2 = _entry(payload={"b": 2, "a": 1})
    assert e1.canonical_bytes() == e2.canonical_bytes()


def test_canonical_bytes_round_trips_through_json():
    """The output is valid JSON — we didn't invent a custom serialization."""
    e = _entry()
    data = json.loads(e.canonical_bytes().decode("utf-8"))
    assert data["actor"] == "operator"
    assert data["action"] == "scan_start"
    assert data["mode"] == "live"


def test_canonical_bytes_is_sorted_keys():
    """Sorted keys are a hard requirement. A reviewer can reproduce the hash
    by calling json.dumps(sort_keys=True) — no Tricorne-specific tooling needed.
    """
    e = _entry()
    raw = e.canonical_bytes().decode("utf-8")
    # Keys in output should be alphabetically sorted at the top level.
    # Find the field ordering by parsing key positions.
    keys_in_order = []
    depth = 0
    in_string = False
    escape = False
    current_key = None
    for i, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    # Simpler check: the top-level keys should appear in sorted order.
    parsed = json.loads(raw)
    assert list(parsed.keys()) == sorted(parsed.keys())


# ---------------------------------------------------------------------------
# append + hash chain integration
# ---------------------------------------------------------------------------

def test_first_append_uses_genesis_hash(tmp_path):
    """A fresh log's first entry has prev_hash == '0' * 64."""
    log_path = tmp_path / "engagement.log"
    entry = log_mod.append(log_path, actor="operator", action="test", payload={})
    assert entry.prev_hash == GENESIS_HASH


def test_second_append_chains_to_first(tmp_path):
    """The second entry's prev_hash equals SHA-256(first.canonical_bytes())."""
    log_path = tmp_path / "engagement.log"
    first = log_mod.append(log_path, actor="operator", action="first", payload={})
    second = log_mod.append(log_path, actor="operator", action="second", payload={})

    expected = log_mod._sha256_hex(first.canonical_bytes())
    assert second.prev_hash == expected


def test_verify_chain_detects_tamper(tmp_path):
    """If someone edits the middle of the log, verify_chain reports which line broke."""
    log_path = tmp_path / "engagement.log"
    log_mod.append(log_path, actor="op", action="a", payload={})
    log_mod.append(log_path, actor="op", action="b", payload={})
    log_mod.append(log_path, actor="op", action="c", payload={})

    # Tamper: rewrite the middle line.
    lines = log_path.read_bytes().splitlines()
    assert len(lines) == 3
    entry = LogEntry.model_validate_json(lines[1])
    tampered = entry.model_copy(update={"action": "TAMPERED"})
    lines[1] = tampered.model_dump_json().encode("utf-8")
    log_path.write_bytes(b"\n".join(lines) + b"\n")

    ok, reason = log_mod.verify_chain(log_path)
    assert ok is False
    assert "line 3" in reason  # the BREAK is detected at line 3's prev_hash check


def test_verify_chain_accepts_clean_log(tmp_path):
    log_path = tmp_path / "engagement.log"
    log_mod.append(log_path, actor="op", action="a", payload={})
    log_mod.append(log_path, actor="op", action="b", payload={})
    ok, _ = log_mod.verify_chain(log_path)
    assert ok is True
