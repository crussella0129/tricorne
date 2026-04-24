# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Contract tests for seal.py security-sensitive primitives.

Covers `_check_not_dev_tainted` (the dev-taint gate — security
boundary) and `_merkle_root` (deterministic, easy to test without
fixtures). Full-flow sealing tests, which require GPG and an
engagement workspace, live in a v0.2 integration test file.
"""

from __future__ import annotations

import hashlib

import pytest

from tricorne_engage import log as log_mod
from tricorne_engage.models import GENESIS_HASH
from tricorne_engage.seal import SealError, _check_not_dev_tainted, _merkle_root


# ---------------------------------------------------------------------------
# _check_not_dev_tainted — security boundary
# ---------------------------------------------------------------------------


def test_empty_or_missing_log_is_not_tainted(tmp_path):
    """A log that never existed — or is empty — cannot carry dev-mode entries."""
    _check_not_dev_tainted(tmp_path / "does-not-exist.log")
    empty = tmp_path / "empty.log"
    empty.write_bytes(b"")
    _check_not_dev_tainted(empty)


def test_live_only_log_passes(tmp_path):
    """A log with only mode: live entries passes the taint gate."""
    log_path = tmp_path / "engagement.log"
    log_mod.append(log_path, actor="op", action="a", payload={}, mode="live")
    log_mod.append(log_path, actor="op", action="b", payload={}, mode="live")
    _check_not_dev_tainted(log_path)  # must not raise


def test_single_dev_entry_fails(tmp_path):
    """A single mode: dev entry anywhere in the log invalidates the seal."""
    log_path = tmp_path / "engagement.log"
    log_mod.append(log_path, actor="op", action="before", payload={}, mode="live")
    log_mod.append(log_path, actor="op", action="devcall", payload={}, mode="dev")
    log_mod.append(log_path, actor="op", action="after", payload={}, mode="live")

    with pytest.raises(SealError) as excinfo:
        _check_not_dev_tainted(log_path)
    assert "dev-mode" in str(excinfo.value)
    assert "line 2" in str(excinfo.value)  # names the offending line


def test_payload_containing_mode_dev_string_does_not_trigger(tmp_path):
    """Regression test for the substring-matching bug (pre-fix of C1).

    A payload VALUE that literally contains the text 'mode:"dev"' must
    not false-positive the taint gate. The gate must inspect the typed
    `mode` field, not do a byte-substring match on the serialized line.
    """
    log_path = tmp_path / "engagement.log"
    log_mod.append(
        log_path,
        actor="op",
        action="note",
        payload={"text": 'we fixed the "mode":"dev" substring bug with typed checks'},
        mode="live",
    )
    _check_not_dev_tainted(log_path)  # must not raise


def test_corrupt_log_line_refuses_seal(tmp_path):
    """An unparseable log line is evidence of tamper or corruption; seal refuses.

    Silently skipping unparseable lines would let an attacker hide a
    dev-mode entry behind a deliberately-corrupted neighbor. Refusal is
    the only safe default.
    """
    log_path = tmp_path / "engagement.log"
    log_mod.append(log_path, actor="op", action="valid", payload={}, mode="live")
    with log_path.open("ab") as fh:
        fh.write(b"{this is not valid json\n")

    with pytest.raises(SealError) as excinfo:
        _check_not_dev_tainted(log_path)
    assert "unparseable" in str(excinfo.value)


# ---------------------------------------------------------------------------
# _merkle_root — deterministic hash over leaf list
# ---------------------------------------------------------------------------


def test_merkle_root_empty_returns_genesis():
    """An empty workspace's Merkle root is the GENESIS sentinel — downstream
    validators always see a 64-char hex string, no None handling needed."""
    assert _merkle_root([]) == GENESIS_HASH


def test_merkle_root_single_leaf_is_the_leaf():
    """A single-leaf tree collapses: the root IS the leaf's hash."""
    leaf = "a" * 64
    assert _merkle_root([leaf]) == leaf


def test_merkle_root_two_leaves_is_hash_of_concatenation():
    """Two leaves: root = SHA-256(leaf1_bytes || leaf2_bytes)."""
    leaf1 = "a" * 64
    leaf2 = "b" * 64
    expected = hashlib.sha256(
        bytes.fromhex(leaf1) + bytes.fromhex(leaf2)
    ).hexdigest()
    assert _merkle_root([leaf1, leaf2]) == expected


def test_merkle_root_odd_count_duplicates_last():
    """Standard Merkle: odd count at any level duplicates the last leaf."""
    leaf = "c" * 64
    # Three leaves [a, b, c]: level 1 should pair (a,b) and (c,c).
    leaves = ["a" * 64, "b" * 64, leaf]
    level1_pair = hashlib.sha256(
        bytes.fromhex(leaves[0]) + bytes.fromhex(leaves[1])
    ).digest()
    level1_dup = hashlib.sha256(bytes.fromhex(leaf) * 2).digest()
    expected = hashlib.sha256(level1_pair + level1_dup).hexdigest()
    assert _merkle_root(leaves) == expected


def test_merkle_root_is_deterministic():
    """Same input, same output, always. Prerequisite for reproducibility."""
    leaves = [format(i, "064x") for i in range(7)]
    assert _merkle_root(leaves) == _merkle_root(leaves)


def test_merkle_root_changes_when_any_leaf_changes():
    """The whole point of a Merkle tree: mutate any leaf, the root changes."""
    leaves = [format(i, "064x") for i in range(5)]
    root1 = _merkle_root(leaves)
    leaves[2] = format(99, "064x")
    root2 = _merkle_root(leaves)
    assert root1 != root2
