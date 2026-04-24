# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Scope matching: is a target in-scope, out-of-scope, or unknown?

The rule is default-deny: out-of-scope wins over in-scope, and
"neither list matches" also means refusal. Tool wrappers must accept
only `ScopeDecision.IN` for unattended execution; `OUT` and `UNKNOWN`
require an explicit `--force-out-of-scope` that is always logged.
"""

from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from tricorne_engage.models import Scope


class ScopeDecision(str, Enum):
    """Result of checking one target against one Scope.

    UNKNOWN is distinct from OUT so that the CLI can surface the right
    error message: OUT means "the scope explicitly excludes this",
    UNKNOWN means "the scope is silent on this" — which for a
    default-deny tool is still a refusal, but with different remediation.
    """

    IN = "in"
    OUT = "out"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScopeResult:
    """The full matcher result: a decision plus the reason.

    The `reason` field goes straight into the log entry payload, so it
    becomes part of the hash-chained audit record. Reviewers six months
    from now will read these reasons; make them informative.
    """

    decision: ScopeDecision
    reason: str


def _classify_target(target: str) -> str:
    """Classify a target string into one of: 'ip', 'url', 'host'.

    Dispatch helper for `is_in_scope` — the matcher needs different
    comparison logic for each kind of target. This helper is small and
    deterministic on purpose; keep it out of Charles's TODO so there is
    no surprise input type to handle.
    """
    try:
        ipaddress.ip_address(target)
        return "ip"
    except ValueError:
        pass

    if "://" in target:
        return "url"
    return "host"


def _ip_in_cidrs(target: str, cidrs: list) -> bool:
    """Return True if `target` (an IP literal) is inside any of the CIDRs."""
    addr = ipaddress.ip_address(target)
    return any(addr in net for net in cidrs)


def _host_matches(target_host: str, host_patterns: list[str]) -> bool:
    """Return True if the host matches any of the configured patterns.

    Supports exact match and fnmatch-style wildcards ("*.acme.example",
    "api.*.acme.example"). Case-insensitive per DNS convention.
    """
    target_lower = target_host.lower()
    return any(
        fnmatch.fnmatchcase(target_lower, pattern.lower()) for pattern in host_patterns
    )


def _url_matches(target_url: str, url_patterns: list[str]) -> bool:
    """Return True if the URL matches any of the configured patterns.

    Design choice (2026-04-24):
      - Scheme-agnostic: http:// vs https:// makes no difference.
        Real-world scope documents say "api.acme.example/v1/*" and mean
        "any scheme, any port, this host, this path prefix."
      - Port is ignored.
      - Host matching: fnmatch (so "*.acme.example" works)
      - Path matching: fnmatch on the path portion
      - Pattern format: "host/path-glob" or "scheme://host/path-glob"
        (scheme, if present, is stripped for comparison)

    A pattern with no `/` is treated as host-only ("api.acme.example"
    matches any URL under api.acme.example regardless of path).
    """
    parsed = urlparse(target_url)
    target_host = parsed.hostname or ""
    target_path = parsed.path or "/"

    for pattern in url_patterns:
        # Strip scheme if present.
        if "://" in pattern:
            pattern = pattern.split("://", 1)[1]

        if "/" not in pattern:
            pattern_host, pattern_path = pattern, "*"
        else:
            pattern_host, pattern_path = pattern.split("/", 1)
            pattern_path = "/" + pattern_path

        if _host_matches(target_host, [pattern_host]) and fnmatch.fnmatchcase(
            target_path, pattern_path
        ):
            return True
    return False


def is_in_scope(target: str, scope: Scope) -> ScopeResult:
    """Decide whether `target` is authorized by `scope`.

    TODO(charles): IMPLEMENT THE BODY — ~8-12 lines.

    THE RULE (default-deny):
      1. Classify the target: IP literal, URL, or hostname.
         Use `_classify_target(target)` — already implemented above.
      2. Check OUT-OF-SCOPE lists for the classified type. If any match,
         return ScopeResult(ScopeDecision.OUT, "explicitly out-of-scope: <detail>").
      3. Check IN-SCOPE lists. If any match, return ScopeResult(
         ScopeDecision.IN, "matched <which pattern>").
      4. Neither list matched: return ScopeResult(ScopeDecision.UNKNOWN,
         "no scope rule matched <target>").

    HELPERS (already implemented — call them, don't rewrite them):
      _ip_in_cidrs(target, scope.out_of_scope_cidr)
      _ip_in_cidrs(target, scope.in_scope_cidr)
      _host_matches(target, scope.out_of_scope_hosts)
      _host_matches(target, scope.in_scope_hosts)
      _url_matches(target, scope.out_of_scope_urls)
      _url_matches(target, scope.in_scope_urls)

    DISPATCH PATTERN:
      kind = _classify_target(target)
      if kind == "ip":
          # consult the _cidr lists
      elif kind == "url":
          # consult the _urls lists
      else:  # "host"
          # consult the _hosts lists

    INVARIANT YOU MUST PRESERVE:
      Out-of-scope is checked FIRST for each type. If a target is in
      BOTH in-scope and out-of-scope, the answer is OUT. This is the
      only safe default for a security tool — scope conflicts must
      fail closed.

    The `reason` string ends up in the engagement log payload and in
    CLI output. Make it specific: include which pattern matched (or
    didn't), and the target itself if space permits. Reviewers read
    these.

    tests/test_scope.py covers:
      - out-of-scope wins over in-scope (the invariant above)
      - IPv4 CIDR containment
      - IPv6 CIDR containment
      - hostname exact match
      - hostname wildcard match
      - URL host+path matching
      - unknown target returns UNKNOWN with a useful reason
    """
    kind = _classify_target(target)

    if kind == "ip":
        # Out-of-scope first per the default-deny invariant.
        if _ip_in_cidrs(target, scope.out_of_scope_cidr):
            matched = _first_matching_cidr(target, scope.out_of_scope_cidr)
            return ScopeResult(
                ScopeDecision.OUT,
                f"{target} matches out-of-scope CIDR {matched}",
            )
        if _ip_in_cidrs(target, scope.in_scope_cidr):
            matched = _first_matching_cidr(target, scope.in_scope_cidr)
            return ScopeResult(
                ScopeDecision.IN,
                f"{target} matches in-scope CIDR {matched}",
            )
        return ScopeResult(
            ScopeDecision.UNKNOWN,
            f"no CIDR rule matches {target}",
        )

    if kind == "url":
        if _url_matches(target, scope.out_of_scope_urls):
            return ScopeResult(
                ScopeDecision.OUT,
                f"{target} matches an out-of-scope URL pattern",
            )
        if _url_matches(target, scope.in_scope_urls):
            return ScopeResult(
                ScopeDecision.IN,
                f"{target} matches an in-scope URL pattern",
            )
        return ScopeResult(
            ScopeDecision.UNKNOWN,
            f"no URL rule matches {target}",
        )

    # kind == "host"
    if _host_matches(target, scope.out_of_scope_hosts):
        return ScopeResult(
            ScopeDecision.OUT,
            f"{target} matches an out-of-scope host pattern",
        )
    if _host_matches(target, scope.in_scope_hosts):
        return ScopeResult(
            ScopeDecision.IN,
            f"{target} matches an in-scope host pattern",
        )
    return ScopeResult(
        ScopeDecision.UNKNOWN,
        f"no host rule matches {target}",
    )


def _first_matching_cidr(target: str, cidrs: list) -> str:
    """Return the string form of the first CIDR in `cidrs` that contains `target`.

    Used only to build informative reason strings after a positive match.
    Separate from `_ip_in_cidrs` because that predicate short-circuits on
    the first hit and doesn't need to carry the matched CIDR back up.
    """
    addr = ipaddress.ip_address(target)
    return next((str(net) for net in cidrs if addr in net), "(unknown)")
