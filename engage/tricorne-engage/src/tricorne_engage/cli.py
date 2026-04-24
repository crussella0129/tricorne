# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""typer-based CLI for tricorne-engage.

Three commands for v0.1 MVP: `new`, `scope`, `seal`. The `log`,
`capture`, and `report` commands are v0.2.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tricorne_engage import __version__
from tricorne_engage import log as log_mod
from tricorne_engage import paths
from tricorne_engage.devmode import (
    compute_mode,
    render_banner,
    require_live_or_dev,
)
from tricorne_engage.models import (
    Engagement,
    EngagementState,
    Scope,
)
from tricorne_engage.seal import SealError, seal as do_seal

app = typer.Typer(
    name="tricorne-engage",
    help="Tricorne Purple Corner engagement workflow.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
)

console = Console()
stderr = Console(stderr=True)


# ----------------------------------------------------------------------------
# Version / banner handling
# ----------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"tricorne-engage {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Top-level callback — runs before every subcommand."""


def _preflight(dev: bool) -> tuple[str, object]:
    """Common setup every command runs. Returns (mode_string, status).

    Computes the mode status, renders the --dev banner if active,
    enforces the "must have SELinux OR --dev" rule. Returns the mode
    string ("live" or "dev") for log entries.
    """
    status = compute_mode(dev)
    render_banner(status, stderr)

    try:
        require_live_or_dev(status)
    except RuntimeError as e:
        stderr.print(f"[bold red]error:[/bold red] {e}")
        raise typer.Exit(code=2) from e

    return ("dev" if status.is_dev else "live"), status


# ----------------------------------------------------------------------------
# new
# ----------------------------------------------------------------------------


@app.command()
def new(
    client_slug: str = typer.Argument(
        ...,
        help="Filesystem-safe identifier for this engagement. e.g. 'acme-webapp-2026'",
    ),
    dev: bool = typer.Option(False, "--dev", help="Enable --dev mode (requires TRICORNE_DEV_MODE=1)."),
) -> None:
    """Create a new engagement workspace under ~/engagements/<client-slug>/."""
    mode, _status = _preflight(dev)

    root = paths.engagement_root(client_slug)
    if root.exists():
        stderr.print(
            f"[bold red]error:[/bold red] engagement '{client_slug}' already exists at {root}"
        )
        raise typer.Exit(code=1)

    # Try to instantiate the Engagement model so we fail fast on bad slugs
    # (pattern validation happens in the model).
    try:
        engagement = Engagement(
            client_slug=client_slug,
            created_at=datetime.now(timezone.utc),
            state=EngagementState.NEW,
        )
    except ValidationError as e:
        stderr.print(f"[bold red]error:[/bold red] invalid slug: {e}")
        raise typer.Exit(code=1) from e

    root.mkdir(parents=True, exist_ok=False)
    paths.artifacts_dir(client_slug).mkdir(parents=True, exist_ok=True)

    metadata_path = paths.engagement_metadata_path(client_slug)
    metadata_path.write_text(
        json.dumps(engagement.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    log_mod.append(
        paths.engagement_log_path(client_slug),
        actor="operator",
        action="engagement_new",
        payload={"slug": client_slug, "version": __version__},
        mode=mode,
    )

    console.print(
        Panel(
            f"Engagement [bold cyan]{client_slug}[/bold cyan] created at\n"
            f"  [dim]{root}[/dim]\n\n"
            "Next step:\n"
            f"  [bold]tricorne-engage scope <scope.json>[/bold]",
            title="[bold green]new engagement[/bold green]",
            border_style="green",
        )
    )


# ----------------------------------------------------------------------------
# scope
# ----------------------------------------------------------------------------


@app.command()
def scope(
    scope_file: Optional[Path] = typer.Argument(
        None,
        help="Scope JSON file to load into the active engagement. Omit to display the current scope.",
    ),
    client_slug: str = typer.Option(
        ...,
        "--engagement", "-e",
        help="Client slug identifying the engagement to scope.",
    ),
    dev: bool = typer.Option(False, "--dev"),
) -> None:
    """Load a scope into an engagement, or display the currently loaded scope."""
    mode, _status = _preflight(dev)

    root = paths.engagement_root(client_slug)
    if not root.exists():
        stderr.print(f"[bold red]error:[/bold red] no engagement '{client_slug}' at {root}")
        raise typer.Exit(code=1)

    target_scope_path = paths.scope_path(client_slug)

    if scope_file is None:
        # Display mode.
        if not target_scope_path.exists():
            stderr.print(
                f"[yellow]no scope loaded yet for '{client_slug}'. "
                "Load one with [bold]tricorne-engage scope <file> -e "
                f"{client_slug}[/bold].[/yellow]"
            )
            raise typer.Exit(code=1)
        loaded = Scope.model_validate_json(target_scope_path.read_text(encoding="utf-8"))
        _render_scope(loaded)
        return

    # Load mode.
    if not scope_file.exists():
        stderr.print(f"[bold red]error:[/bold red] scope file not found: {scope_file}")
        raise typer.Exit(code=1)

    try:
        parsed = Scope.model_validate_json(scope_file.read_text(encoding="utf-8"))
    except (ValidationError, OSError) as e:
        stderr.print(f"[bold red]error:[/bold red] scope file failed validation: {e}")
        raise typer.Exit(code=1) from e

    # Copy into the workspace for provenance — the seal will include it.
    shutil.copy2(scope_file, target_scope_path)

    digest = hashlib.sha256(target_scope_path.read_bytes()).hexdigest()

    log_mod.append(
        paths.engagement_log_path(client_slug),
        actor="operator",
        action="scope_loaded",
        payload={
            "source_path": str(scope_file.resolve()),
            "sha256": digest,
            "in_scope_count": (
                len(parsed.in_scope_cidr)
                + len(parsed.in_scope_hosts)
                + len(parsed.in_scope_urls)
            ),
            "out_of_scope_count": (
                len(parsed.out_of_scope_cidr)
                + len(parsed.out_of_scope_hosts)
                + len(parsed.out_of_scope_urls)
            ),
        },
        mode=mode,
    )

    console.print(
        Panel(
            f"Scope loaded for [bold cyan]{client_slug}[/bold cyan]\n"
            f"  source: [dim]{scope_file}[/dim]\n"
            f"  sha256: [dim]{digest}[/dim]",
            title="[bold green]scope loaded[/bold green]",
            border_style="green",
        )
    )


def _render_scope(s: Scope) -> None:
    """Pretty-print a loaded scope."""
    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold")
    header.add_column()
    header.add_row("Engagement:", s.engagement)
    header.add_row("Client:", s.client)
    header.add_row("Authorized from:", s.authorized_from.isoformat())
    header.add_row("Authorized to:", s.authorized_to.isoformat())
    console.print(header)
    console.print()

    in_tab = Table(title="In scope", show_lines=False, border_style="green")
    in_tab.add_column("Type")
    in_tab.add_column("Entry")
    for c in s.in_scope_cidr:
        in_tab.add_row("CIDR", str(c))
    for h in s.in_scope_hosts:
        in_tab.add_row("Host", h)
    for u in s.in_scope_urls:
        in_tab.add_row("URL", u)
    console.print(in_tab)

    out_tab = Table(title="Out of scope", show_lines=False, border_style="red")
    out_tab.add_column("Type")
    out_tab.add_column("Entry")
    for c in s.out_of_scope_cidr:
        out_tab.add_row("CIDR", str(c))
    for h in s.out_of_scope_hosts:
        out_tab.add_row("Host", h)
    for u in s.out_of_scope_urls:
        out_tab.add_row("URL", u)
    console.print(out_tab)


# ----------------------------------------------------------------------------
# seal
# ----------------------------------------------------------------------------


@app.command()
def seal(
    client_slug: str = typer.Option(
        ...,
        "--engagement", "-e",
        help="Client slug identifying the engagement to seal.",
    ),
    confirm: bool = typer.Option(
        False, "--confirm", help="Required. Sealing is irreversible."
    ),
    dev: bool = typer.Option(False, "--dev"),
) -> None:
    """Seal an engagement workspace into a signed, hashed evidence artifact."""
    mode, _status = _preflight(dev)

    if not confirm:
        stderr.print(
            "[yellow]seal requires [bold]--confirm[/bold]. Sealing is irreversible "
            "and the workspace cannot be modified afterward.[/yellow]"
        )
        raise typer.Exit(code=1)

    root = paths.engagement_root(client_slug)
    if not root.exists():
        stderr.print(f"[bold red]error:[/bold red] no engagement '{client_slug}' at {root}")
        raise typer.Exit(code=1)

    metadata_path = paths.engagement_metadata_path(client_slug)
    try:
        engagement = Engagement.model_validate_json(
            metadata_path.read_text(encoding="utf-8")
        )
    except (ValidationError, OSError) as e:
        stderr.print(f"[bold red]error:[/bold red] corrupt engagement metadata: {e}")
        raise typer.Exit(code=1) from e

    try:
        result = do_seal(engagement)
    except SealError as e:
        stderr.print(f"[bold red]seal failed:[/bold red] {e}")
        raise typer.Exit(code=3) from e
    except NotImplementedError as e:
        # Most likely hit if Charles's TODO in log.py or scope.py isn't filled in yet.
        stderr.print(
            f"[bold red]seal failed:[/bold red] {e}\n"
            "[dim]One of the TODO(charles) functions needs implementation. "
            "See models.py, scope.py, and log.py.[/dim]"
        )
        raise typer.Exit(code=4) from e

    # Update engagement state.
    engagement = engagement.model_copy(update={"state": EngagementState.SEALED})
    metadata_path.write_text(
        json.dumps(engagement.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    console.print(
        Panel(
            f"Engagement [bold cyan]{client_slug}[/bold cyan] sealed.\n\n"
            f"  [bold]artifact:[/bold]  [green]{result.tarball_path}[/green]\n"
            f"  [bold]merkle root:[/bold] [dim]{result.merkle_root_hex}[/dim]\n"
            f"  [bold]signed by:[/bold]   [dim]{result.signature_fingerprint}[/dim]\n"
            f"  [bold]index line:[/bold]  {'yes' if result.index_line_appended else 'NO — check engagement-index.jsonl'}",
            title="[bold green]seal complete[/bold green]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
