# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for engagement state.

On-disk format is strict JSON (design decision 2026-04-24 — see
engage/tricorne-engage/README.md "On-disk formats"). No YAML, no TOML,
no JSONC. Human annotations that would otherwise need `# comments`
live in the structured `ScopeNotes.entries` field defined below.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from ipaddress import IPv4Network, IPv6Network
from typing import Annotated, Literal, Union

from pydantic import AwareDatetime, BaseModel, Field, IPvAnyNetwork

# Every timestamp in Tricorne's on-disk format MUST be timezone-aware. A
# naive datetime serializes as "2026-04-25T09:00:00" (no offset), which is
# evidence-hostile — a reviewer cannot tell whether the value is UTC, local
# to the operator's workstation, or local to some other zone. AwareDatetime
# is a pydantic v2 type that rejects naive datetimes at validation time.
# See README §"On-disk formats".


# Pydantic in v2 uses discriminated unions for type narrowing. For
# simplicity, we union IPv4Network + IPv6Network here. Pydantic's
# IPvAnyNetwork provides broad validation of "is this a CIDR string".
CidrNetwork = Annotated[Union[IPv4Network, IPv6Network], IPvAnyNetwork]


class EngagementState(str, Enum):
    """Lifecycle states. The happy path is NEW -> SCOPED -> SEALED."""

    NEW = "new"              # created, no scope loaded yet
    SCOPED = "scoped"        # scope loaded, work in progress
    SEALING = "sealing"      # seal in progress (transient, should never persist)
    SEALED = "sealed"        # sealed; workspace is now read-only


class Engagement(BaseModel):
    """Top-level engagement metadata. Lives at engagement.json."""

    client_slug: str = Field(
        ...,
        description="Filesystem-safe identifier. [a-z0-9][a-z0-9-]*",
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        min_length=1,
        max_length=64,
    )
    created_at: AwareDatetime
    state: EngagementState = EngagementState.NEW
    schema_version: int = Field(default=1, description="Bump on incompatible format changes.")


class ScopeNote(BaseModel):
    """A single annotation attached to a scope.

    TODO(charles): FILL IN THIS MODEL — ~5 lines of pydantic.

    Design context: we chose strict JSON (no `//` comments) for scope
    files on 2026-04-24. That means annotations — "why was this
    excluded?", "who approved that?" — need a structured home. Six
    months from now, a reviewer will want to know who added what and
    when. Without this, scope provenance gets lost the moment the
    original operator rotates off the engagement.

    Required fields (your call on the types and exact names):
      ts       — datetime, tz-aware, when the note was written
      author   — string identifying who wrote it
                 YOU DECIDE: bare name? email? GPG fingerprint?
      text     — the annotation body; non-empty string
      refs     — list of scope-entry identifiers this note applies to;
                 empty list means "general note, not tied to a specific entry"

    Pydantic v2 syntax reference:

        class Foo(BaseModel):
            field_name: type                           # required
            with_default: str = "default value"        # defaulted
            with_validation: str = Field(
                default="x",
                min_length=1,
                description="why this field exists",
            )

    Validators (optional, but encouraged for `author` if you pick a
    specific format):

        from pydantic import field_validator
        @field_validator("author")
        @classmethod
        def _author_must_have_shape(cls, v: str) -> str:
            ...

    tests/test_scope.py carries a `test_scope_note_has_fields` test
    that will red-green as you fill this in.
    """

    # Author format deliberately loose for v0.1 MVP — bare strings. In
    # practice operators will use their email, their GPG fingerprint, or
    # a service-account slug; pinning one now would be premature. v0.2
    # can add a validator once we see how the field actually gets used.
    ts: AwareDatetime
    author: str = Field(
        ...,
        min_length=1,
        description="Operator identity: name, email, or GPG fingerprint.",
    )
    text: str = Field(..., min_length=1, description="The annotation body.")
    refs: list[str] = Field(
        default_factory=list,
        description=(
            "Scope-entry identifiers this note attaches to (e.g. the string "
            "form of a CIDR, a host pattern, a URL pattern). Empty means "
            "the note is general and does not target a specific entry."
        ),
    )


class ScopeNotes(BaseModel):
    """Container for all annotations on a scope. Structured list, not free text."""

    entries: list[ScopeNote] = Field(default_factory=list)


class Scope(BaseModel):
    """An engagement's authorization boundary.

    Loaded from scope.json in the engagement root. Out-of-scope wins
    over in-scope; see scope.py::is_in_scope for the matcher.
    """

    engagement: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]*$")
    client: str = Field(..., min_length=1)
    authorized_from: AwareDatetime
    authorized_to: AwareDatetime

    in_scope_cidr: list[CidrNetwork] = Field(default_factory=list)
    in_scope_hosts: list[str] = Field(default_factory=list)
    in_scope_urls: list[str] = Field(default_factory=list)

    out_of_scope_cidr: list[CidrNetwork] = Field(default_factory=list)
    out_of_scope_hosts: list[str] = Field(default_factory=list)
    out_of_scope_urls: list[str] = Field(default_factory=list)

    notes: ScopeNotes = Field(default_factory=ScopeNotes)


class LogEntry(BaseModel):
    """A single line in the engagement log (JSON Lines format, hash-chained).

    Each entry's `prev_hash` is the hex SHA-256 of the previous entry's
    `canonical_bytes()`. First entry uses GENESIS_HASH.

    Fields intentionally shallow and sorted lexicographically in the
    canonical form — no nested structure in the top level — so any
    language can replay the chain without needing our particular
    canonicalization implementation. Action-specific details go in
    `payload`, which is allowed to be any JSON-serializable dict.
    """

    ts: AwareDatetime
    actor: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1, description="Machine-readable verb, e.g. 'scan_start'.")
    mode: Literal["live", "dev"] = "live"
    payload: dict = Field(default_factory=dict)
    prev_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    def canonical_bytes(self) -> bytes:
        """Return the canonical byte representation used for hashing.

        TODO(charles): IMPLEMENT THIS — ~5 lines.

        THE CONTRACT:
          - Two LogEntry instances with equal field values must produce
            equal bytes. This is the invariant the hash chain depends on.
          - The output must be stable across Python versions, machine
            architectures, and dict insertion orders.
          - datetime fields must serialize as RFC 3339 strings with
            timezone ("YYYY-MM-DDTHH:MM:SS+00:00", NOT "Z" — pydantic's
            default tz format keeps the explicit offset).

        RECOMMENDED APPROACH:
          1. `self.model_dump(mode="json")` — pydantic handles datetime
             serialization correctly, giving you a plain dict.
          2. `json.dumps(..., sort_keys=True, separators=(",", ":"),
             ensure_ascii=False)` — sorted keys recursively, no
             whitespace, UTF-8-safe.
          3. `.encode("utf-8")` — bytes, not str.

        WATCH OUT:
          - `sort_keys=True` on json.dumps sorts at all levels for you.
            You don't need a recursive walker.
          - `separators=(",", ":")` matters — the default separator
            includes spaces, which would break hash stability.
          - `ensure_ascii=False` keeps non-ASCII characters in their
            natural UTF-8 encoding. `ensure_ascii=True` would escape
            them, which is also stable but larger; pick one and stick
            with it. The reference implementation uses False.

        tests/test_log.py has `test_canonical_bytes_stable` asserting
        the "same data -> same bytes" contract and a property-style
        test ensuring canonical JSON can be round-tripped through
        json.loads without loss.
        """
        # Pydantic's model_dump(mode="json") serializes datetimes as
        # ISO 8601 strings and any nested pydantic models as plain
        # dicts — leaving us with a JSON-ready value tree. Passing it
        # through json.dumps with sort_keys=True (recursive) and the
        # tightest separators gives a single canonical byte form per
        # logical entry.
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")


#: The hex SHA-256 placeholder used as prev_hash on the first log entry.
GENESIS_HASH = "0" * 64


class SealManifestFile(BaseModel):
    """One file's entry in a seal manifest."""

    path: str                     # relative to the engagement root, forward-slashed
    size: int
    mode: int                     # POSIX mode bits; 0 on Windows dev runs
    sha256_hex: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    selinux_context: str | None = None   # None on non-SELinux hosts (--dev)


class SealManifest(BaseModel):
    """The full manifest produced during sealing. See seal.py."""

    schema_version: int = 1
    engagement_slug: str
    sealed_at: AwareDatetime
    files: list[SealManifestFile]
    merkle_root_hex: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    final_log_hash_hex: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    operator_gpg_fingerprint: str | None = None
