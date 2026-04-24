# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""`--dev` mode gate and SELinux environment detection.

Security rationale for the two-key design lives in the project-level
`engage/tricorne-engage/README.md` under "--dev mode". This module
enforces those rules at runtime.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel

DEV_ENV_VAR = "TRICORNE_DEV_MODE"
DEV_ENV_VALUE = "1"


class SELinuxState(str, Enum):
    """What getenforce / /sys/fs/selinux/enforce tell us about the host."""

    ENFORCING = "enforcing"
    PERMISSIVE = "permissive"
    DISABLED = "disabled"
    NOT_AVAILABLE = "not_available"


@dataclass(frozen=True)
class ModeStatus:
    """Computed activation state for a CLI invocation.

    `is_dev` is the truth source: True means the log entries emitted by
    this process will carry `mode: "dev"` and `seal` will refuse to
    finalize the workspace.
    """

    flag_passed: bool
    env_set: bool
    is_dev: bool
    selinux: SELinuxState
    reason: str

    @property
    def is_no_op(self) -> bool:
        """True when dev mode was requested but kernel enforcement is live.

        On a Tricorne system with SELinux enforcing, requesting --dev is
        harmless — the kernel checks fire regardless of flag. We still
        report the mode so log entries carry accurate provenance.
        """
        return self.is_dev and self.selinux is SELinuxState.ENFORCING


def probe_selinux() -> SELinuxState:
    """Report the SELinux state of the running host.

    Preferred source is /sys/fs/selinux/enforce (single byte: 0 or 1) —
    it is fast, doesn't require subprocess, and is unambiguous. Fall back
    to `getenforce` if the sysfs file isn't readable. On hosts without
    SELinux (Windows, macOS, most container dev environments), both
    probes fail cleanly and we report NOT_AVAILABLE.
    """
    sysfs_path = "/sys/fs/selinux/enforce"
    try:
        with open(sysfs_path, "rb") as fh:
            byte = fh.read(1)
        if byte == b"1":
            return SELinuxState.ENFORCING
        if byte == b"0":
            return SELinuxState.PERMISSIVE
    except OSError:
        pass

    try:
        result = subprocess.run(
            ["getenforce"], capture_output=True, text=True, timeout=2, check=False
        )
        output = result.stdout.strip().lower()
        if output == "enforcing":
            return SELinuxState.ENFORCING
        if output == "permissive":
            return SELinuxState.PERMISSIVE
        if output == "disabled":
            return SELinuxState.DISABLED
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return SELinuxState.NOT_AVAILABLE


def compute_mode(flag_passed: bool) -> ModeStatus:
    """Combine flag + env var + SELinux state into a ModeStatus.

    The rule is: dev mode is active only when BOTH the --dev flag is
    passed AND the TRICORNE_DEV_MODE environment variable is set to "1".
    One without the other is not enough — this is the two-key activation
    that prevents accidental dev mode in a real engagement shell.
    """
    env_value = os.environ.get(DEV_ENV_VAR)
    env_set = env_value == DEV_ENV_VALUE
    is_dev = flag_passed and env_set

    if is_dev:
        reason = "both --dev flag and TRICORNE_DEV_MODE=1 present"
    elif flag_passed and not env_set:
        reason = (
            f"--dev flag was passed but {DEV_ENV_VAR} is not set to {DEV_ENV_VALUE!r}; "
            "dev mode requires both"
        )
    elif env_set and not flag_passed:
        reason = (
            f"{DEV_ENV_VAR}={DEV_ENV_VALUE} is set but --dev flag was not passed; "
            "dev mode requires both"
        )
    else:
        reason = "live mode"

    return ModeStatus(
        flag_passed=flag_passed,
        env_set=env_set,
        is_dev=is_dev,
        selinux=probe_selinux(),
        reason=reason,
    )


def render_banner(status: ModeStatus, console: Console | None = None) -> None:
    """Print the --dev warning banner. Called on every command invocation.

    We intentionally re-print on every command (not once per session) so
    that operators screen-sharing or reviewing recordings can't miss it,
    and so log captures always show the mode context.
    """
    if not status.is_dev:
        return

    c = console or Console(stderr=True)
    lines = [
        "[bold white on red] DEV MODE ACTIVE [/bold white on red]",
        "",
        "Requires both [bold]--dev[/bold] flag AND "
        f"[bold]{DEV_ENV_VAR}=1[/bold] environment variable.",
        "Log entries from this process carry [bold]mode: \"dev\"[/bold].",
        "[bold red]`tricorne-engage seal` will refuse any workspace with dev entries.[/bold red]",
    ]
    if status.is_no_op:
        lines.append("")
        lines.append(
            "[dim]Note: SELinux is enforcing on this host; "
            "real checks still fire at the kernel regardless of this flag.[/dim]"
        )
    lines.append("[bold yellow]NOT SAFE FOR REAL ENGAGEMENTS.[/bold yellow]")

    c.print(
        Panel(
            "\n".join(lines),
            border_style="red",
            title="[bold red]tricorne-engage[/bold red]",
            title_align="left",
        )
    )


def require_live_or_dev(status: ModeStatus) -> None:
    """Enforce the "must have real SELinux OR an explicit --dev" rule.

    If SELinux is not available (dev workstation) and dev mode is not
    active, abort. This is the forcing function that makes Windows and
    macOS users pass --dev explicitly rather than silently drift into an
    unauthenticated, unenforced run.
    """
    if status.is_dev:
        return
    if status.selinux is SELinuxState.ENFORCING:
        return
    # Permissive / disabled / not-available on a non-dev invocation.
    # Let the CLI surface a clear error.
    raise RuntimeError(
        f"SELinux is {status.selinux.value} and --dev was not requested. "
        f"Pass --dev and set {DEV_ENV_VAR}=1 to run on a non-enforcing host. "
        "See engage/tricorne-engage/README.md '#--dev mode'."
    )
