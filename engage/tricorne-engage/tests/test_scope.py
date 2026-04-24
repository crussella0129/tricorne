# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Contract tests for scope.py::is_in_scope.

Each test documents ONE rule the matcher must satisfy. All tests
currently fail with NotImplementedError; they go green as Charles
fills in the TODO in scope.py. The test names are the spec.
"""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import IPv4Network, IPv6Network

import pytest

from tricorne_engage.models import Scope
from tricorne_engage.scope import ScopeDecision, is_in_scope


def _scope(**overrides) -> Scope:
    """Build a minimal Scope with all the defaults, overriding specific fields."""
    defaults = dict(
        engagement="test-engagement",
        client="Test Client",
        authorized_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        authorized_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Scope(**defaults)


# ---------------------------------------------------------------------------
# The invariant: out-of-scope wins over in-scope
# ---------------------------------------------------------------------------

def test_out_of_scope_wins_over_in_scope_for_ip():
    """If a target is in BOTH lists, the answer is OUT. Default-deny."""
    s = _scope(
        in_scope_cidr=[IPv4Network("10.0.0.0/8")],
        out_of_scope_cidr=[IPv4Network("10.1.0.0/16")],
    )
    result = is_in_scope("10.1.2.3", s)
    assert result.decision == ScopeDecision.OUT


def test_out_of_scope_wins_over_in_scope_for_host():
    s = _scope(
        in_scope_hosts=["*.acme.example"],
        out_of_scope_hosts=["vpn.acme.example"],
    )
    assert is_in_scope("vpn.acme.example", s).decision == ScopeDecision.OUT


# ---------------------------------------------------------------------------
# IPv4 / IPv6 CIDR matching
# ---------------------------------------------------------------------------

def test_ipv4_cidr_in_scope():
    s = _scope(in_scope_cidr=[IPv4Network("203.0.113.0/24")])
    assert is_in_scope("203.0.113.42", s).decision == ScopeDecision.IN


def test_ipv4_cidr_out_of_scope():
    s = _scope(out_of_scope_cidr=[IPv4Network("203.0.113.0/24")])
    assert is_in_scope("203.0.113.42", s).decision == ScopeDecision.OUT


def test_ipv6_cidr_in_scope():
    s = _scope(in_scope_cidr=[IPv6Network("2001:db8::/32")])
    assert is_in_scope("2001:db8::1", s).decision == ScopeDecision.IN


def test_ip_not_in_any_cidr_is_unknown():
    s = _scope(in_scope_cidr=[IPv4Network("203.0.113.0/24")])
    assert is_in_scope("198.51.100.7", s).decision == ScopeDecision.UNKNOWN


# ---------------------------------------------------------------------------
# Host matching (exact and wildcard)
# ---------------------------------------------------------------------------

def test_host_exact_match():
    s = _scope(in_scope_hosts=["api.acme.example"])
    assert is_in_scope("api.acme.example", s).decision == ScopeDecision.IN


def test_host_wildcard_match():
    s = _scope(in_scope_hosts=["*.acme.example"])
    assert is_in_scope("whatever.acme.example", s).decision == ScopeDecision.IN


def test_host_wildcard_does_not_match_parent_domain():
    """'*.acme.example' matches api.acme.example but NOT acme.example."""
    s = _scope(in_scope_hosts=["*.acme.example"])
    assert is_in_scope("acme.example", s).decision == ScopeDecision.UNKNOWN


def test_host_matching_is_case_insensitive():
    s = _scope(in_scope_hosts=["API.Acme.Example"])
    assert is_in_scope("api.acme.example", s).decision == ScopeDecision.IN


# ---------------------------------------------------------------------------
# URL matching
# ---------------------------------------------------------------------------

def test_url_host_path_match():
    s = _scope(in_scope_urls=["api.acme.example/v1/*"])
    assert is_in_scope("https://api.acme.example/v1/users", s).decision == ScopeDecision.IN


def test_url_match_is_scheme_agnostic():
    """The http/https split is a deployment detail, not a scope boundary."""
    s = _scope(in_scope_urls=["api.acme.example/*"])
    assert is_in_scope("http://api.acme.example/", s).decision == ScopeDecision.IN
    assert is_in_scope("https://api.acme.example/", s).decision == ScopeDecision.IN


def test_url_path_mismatch_is_unknown():
    s = _scope(in_scope_urls=["api.acme.example/v1/*"])
    assert is_in_scope("https://api.acme.example/v2/users", s).decision == ScopeDecision.UNKNOWN


# ---------------------------------------------------------------------------
# Reason strings are informative
# ---------------------------------------------------------------------------

def test_reason_identifies_the_matched_rule_for_in_scope():
    s = _scope(in_scope_cidr=[IPv4Network("10.0.0.0/8")])
    result = is_in_scope("10.1.2.3", s)
    assert result.decision == ScopeDecision.IN
    # We don't pin exact wording (Charles's implementation choice), but the
    # reason should reference the target or the rule so reviewers know WHY
    # the call succeeded.
    assert "10.1.2.3" in result.reason or "10.0.0.0" in result.reason


def test_reason_identifies_the_target_for_unknown():
    s = _scope()  # empty scope
    result = is_in_scope("10.0.0.1", s)
    assert result.decision == ScopeDecision.UNKNOWN
    assert "10.0.0.1" in result.reason
