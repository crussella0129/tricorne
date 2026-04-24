# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Filesystem layout for tricorne-engage.

All paths on disk are defined here, in one place, so a future change
(e.g., XDG compliance, alternate roots for testing) doesn't require
hunting through the whole package. Follow Fedora's FHS conventions:
engagements live under HOME, state under $XDG_STATE_HOME, never
/opt/tricorne or similar.
"""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    """The operator's HOME. Overridable via $TRICORNE_ENGAGE_HOME for tests."""
    override = os.environ.get("TRICORNE_ENGAGE_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home()


def engagements_dir() -> Path:
    """Live engagement workspaces. One subdirectory per client slug.

    On a Tricorne system, this directory is labeled `tricorne_home_t`
    (see selinux/tricorne-base/tricorne.fc). On dev systems, labels
    don't apply but the layout is identical so sealed artifacts are
    portable between them.
    """
    return home() / "engagements"


def sealed_dir() -> Path:
    """Read-only sealed artifacts, labeled `tricorne_report_t` on Tricorne.

    Nothing under this directory should ever be written by operator
    tools except `tricorne-engage seal` itself.
    """
    return home() / "engagements-sealed"


def state_dir() -> Path:
    """$XDG_STATE_HOME/tricorne, for data that survives seals and engagements.

    Contains the external engagement index (see engagement_index_path),
    active-engagement pointer, and future cached state.
    """
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state).expanduser() if xdg_state else home() / ".local" / "state"
    return base / "tricorne"


def engagement_root(client_slug: str) -> Path:
    """Directory for a specific engagement."""
    return engagements_dir() / client_slug


def engagement_metadata_path(client_slug: str) -> Path:
    """JSON file holding engagement metadata (slug, created_at, state)."""
    return engagement_root(client_slug) / "engagement.json"


def scope_path(client_slug: str) -> Path:
    """JSON scope file. Absent until `tricorne-engage scope <file>` runs."""
    return engagement_root(client_slug) / "scope.json"


def engagement_log_path(client_slug: str) -> Path:
    """JSON Lines engagement log. Append-only, hash-chained."""
    return engagement_root(client_slug) / "engagement.log"


def artifacts_dir(client_slug: str) -> Path:
    """Where tool output, screenshots, and evidence live within an engagement."""
    return engagement_root(client_slug) / "artifacts"


def seal_lock_path(client_slug: str) -> Path:
    """Transient marker indicating a seal is in progress. If this file exists
    at engagement start, the previous seal crashed partway through and the
    workspace is in an unknown state. CLI refuses to proceed until resolved."""
    return engagement_root(client_slug) / ".seal" / "pid"


def engagement_index_path() -> Path:
    """External engagement index, outside any individual engagement workspace.

    A single append-only JSON Lines file recording every seal operation.
    Survives even if a sealed tarball is lost; proves the seal happened.
    """
    return state_dir() / "engagement-index.jsonl"


def active_engagement_pointer() -> Path:
    """Symlink (Unix) or file (Windows) naming the active engagement.

    Set by `tricorne-engage new` and `tricorne-engage use`. Used by
    wrapper scripts around nmap/ffuf/etc. to find the active scope
    without requiring every invocation to pass `--engagement`.
    """
    return state_dir() / "active-engagement"


def ensure_state_dir() -> Path:
    """Make sure state_dir() exists. Returns the path."""
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d
