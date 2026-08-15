"""Kryon CLI — the main command surface (Typer).

File #0 added the ``--version`` flag and the ``emit-test-event`` smoke
command. File #1 adds the ``config`` and ``secrets`` sub-apps so the
user can manage configuration and encrypted API keys. Subsequent
files will add ``hunt``, ``logs``, ``activity``, ``targets``, ``report``,
``audit``, ``learn``, ``tui``, and ``dry-run``.
"""

from __future__ import annotations

import asyncio
import getpass
import io
import sys
from typing import Any

import typer
import yaml
from rich.console import Console

from kryon import __version__
from kryon.activity import emit_subagent_end, emit_subagent_start, setup_activity
from kryon.core.config import (
    KryonConfig,
    load_config,
    save_config,
    set_config_value,
)
from kryon.core.exceptions import ConfigError, SecretError
from kryon.core.logger import setup_logging
from kryon.core.paths import kryon_config_file
from kryon.core.secrets import (
    delete_secret,
    get_secret,
    list_secrets,
    set_secret,
)
from kryon.targets import (
    get_target_manager,
    parse_scope_string,
    reset_target_manager,
)


def _ensure_utf8_stdout() -> None:
    """Force UTF-8 encoding on stdout/stderr.

    Windows legacy consoles default to cp1252, which can't encode
    the 🐙 emoji in our version banner or the ✅/🛑/❌ glyphs in
    activity events. Reconfiguring the streams at startup is the
    standard cross-platform fix; on non-Windows this is a no-op.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:  # Python 3.7+
            try:
                reconfigure(encoding="utf-8")
                continue
            except (AttributeError, io.UnsupportedOperation):
                pass
        # Fallback: wrap the underlying buffer
        buf = getattr(stream, "buffer", None)
        if buf is not None:
            setattr(
                sys,
                stream_name,
                io.TextIOWrapper(buf, encoding="utf-8", line_buffering=True),
            )


_ensure_utf8_stdout()

app = typer.Typer(
    name="kryon",
    help="🐙 Kryon: hypothesis-driven autonomous security agent",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

# Sub-apps
config_app = typer.Typer(help="View and modify configuration.", rich_markup_mode="rich")
secrets_app = typer.Typer(help="Manage encrypted secrets.", rich_markup_mode="rich")
app.add_typer(config_app, name="config")
app.add_typer(secrets_app, name="secrets")
targets_app = typer.Typer(help="Manage targets.", rich_markup_mode="rich")
app.add_typer(targets_app, name="targets")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"🐙 Kryon v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: ARG001 — used via typer callback
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress activity stream"),
) -> None:
    """Kryon: hypothesis-driven autonomous security agent."""
    setup_logging(level="DEBUG" if verbose else "INFO")
    setup_activity(verbose=not quiet)


# ---------------------------------------------------------------------------
# File #0 command: emit-test-event
# ---------------------------------------------------------------------------


@app.command()
def emit_test_event() -> None:
    """Emit a test event to verify the activity system is working."""
    asyncio.run(_emit_test_event_async())


async def _emit_test_event_async() -> None:
    target_id = "test-target"
    await emit_subagent_start(
        subagent="test",
        target_id=target_id,
        goal="verify the activity system works",
        iteration=1,
    )
    await emit_subagent_end(
        subagent="test",
        target_id=target_id,
        status="success",
        entities_added=0,
        cost_usd=0.0,
        duration_ms=42,
    )
    console.print("[green]✅ Test event emitted. Check ~/.kryon/logs/activity.jsonl[/green]")


# ---------------------------------------------------------------------------
# File #1: `kryon config` sub-app
# ---------------------------------------------------------------------------


def _redact_secrets(obj: Any) -> Any:
    """Recursively redact SecretStr-shaped values from a config dump.

    Pydantic's ``model_dump(mode='json')`` already serializes
    ``SecretStr`` to ``"**********"``, but this function adds a
    second layer: any key whose name contains ``secret`` (case
    insensitive) or whose value is the redacted placeholder gets
    replaced with ``"***"`` for display. This is defense in depth
    so a future Pydantic change can't accidentally expose a real
    secret in ``kryon config show`` output.
    """
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(v, str) and (
                "secret" in k.lower()
                or v == "**********"
                or "token" in k.lower()
                or "password" in k.lower()
            ):
                result[k] = "***"
            else:
                result[k] = _redact_secrets(v)
        return result
    if isinstance(obj, list):
        return [_redact_secrets(i) for i in obj]
    return obj


@config_app.command("init")
def config_init() -> None:
    """Create the default config at ~/.kryon/config.yaml if missing.

    Refuses to overwrite an existing file.
    """
    path = kryon_config_file()
    if path.exists():
        console.print(f"[yellow]Config already exists at {path}[/yellow]")
        raise typer.Exit(1)
    config = KryonConfig()
    save_config(config)
    console.print(f"[green]✅ Created config at {path}[/green]")


@config_app.command("show")
def config_show() -> None:
    """Show the active configuration (secrets redacted)."""
    config = load_config()
    data = config.model_dump(mode="json")
    redacted = _redact_secrets(data)
    console.print(
        yaml.safe_dump(redacted, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )


@config_app.command("validate")
def config_validate() -> None:
    """Validate the active configuration."""
    try:
        config = load_config()
    except ConfigError as e:
        console.print(f"[red]❌ Configuration is invalid:[/red] {e}")
        raise typer.Exit(1) from e
    console.print("[green]✅ Configuration is valid[/green]")
    console.print(f"  LLM: {config.llm.provider}/{config.llm.model}")
    console.print(f"  Default budget: ${config.cost.default_per_target_usd}")
    if config.llm.base_url:
        console.print(f"  Base URL: {config.llm.base_url}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Dot-notation key, e.g. llm.provider"),
    value: str = typer.Argument(..., help="Value to set (coerced to int/float/bool)"),
) -> None:
    """Set a single config value using dot notation.

    Examples::

        kryon config set llm.provider ollama
        kryon config set llm.model llama3.1:8b
        kryon config set cost.default_per_target_usd 5
    """
    config = load_config()
    try:
        new_config = set_config_value(config, key, value)
    except ConfigError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1) from e
    save_config(new_config)
    console.print(f"[green]✅ Set {key} = {value}[/green]")


# ---------------------------------------------------------------------------
# File #1: `kryon secrets` sub-app
# ---------------------------------------------------------------------------


@secrets_app.command("set")
def secrets_set(
    name: str = typer.Argument(..., help="Secret name (e.g. anthropic_api_key)"),
    value: str | None = typer.Argument(
        None,
        help="Secret value. Use '-' to read from stdin, or omit to prompt securely.",
    ),
) -> None:
    """Store an encrypted secret."""
    if value == "-":
        value = sys.stdin.read().strip()
    elif value is None:
        value = getpass.getpass(f"Enter value for {name}: ")
    try:
        set_secret(name, value)
    except SecretError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]✅ Stored secret: {name}[/green]")


@secrets_app.command("get")
def secrets_get(name: str = typer.Argument(...)) -> None:
    """Retrieve and display a secret (with confirmation)."""
    if not typer.confirm(f"Print the value of secret '{name}' to the terminal?"):
        raise typer.Abort()
    try:
        value = get_secret(name)
    except SecretError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1) from e
    console.print(value)


@secrets_app.command("delete")
def secrets_delete(name: str = typer.Argument(...)) -> None:
    """Delete a secret (with confirmation)."""
    if not typer.confirm(f"Delete secret '{name}'?"):
        raise typer.Abort()
    if delete_secret(name):
        console.print(f"[green]✅ Deleted secret: {name}[/green]")
    else:
        console.print(f"[yellow]Secret {name} did not exist[/yellow]")


@secrets_app.command("list")
def secrets_list() -> None:
    """List all stored secret names (values are NEVER displayed)."""
    keys = list_secrets()
    if not keys:
        console.print("[dim]No secrets stored yet.[/dim]")
        return
    for k in sorted(keys):
        console.print(f"  • {k}")


# ---------------------------------------------------------------------------
# File #3: `kryon targets` sub-app
# ---------------------------------------------------------------------------


@targets_app.command("create")
def targets_create(
    slug: str = typer.Argument(..., help="Target slug (e.g., 'example')"),
    name: str = typer.Option(..., "--name", "-n", help="Display name"),
    mode: str = typer.Option(..., "--mode", "-m", help="purple_team or bug_bounty"),
    domains: str = typer.Option(
        "",
        "--domains",
        "-d",
        help="Comma-separated domains (use '*.example.com' for wildcard)",
    ),
    ips: str = typer.Option("", "--ips", help="Comma-separated IPs/CIDRs"),
    ports: str = typer.Option("80,443", "--ports", help="Comma-separated allowed ports"),
    budget: float = typer.Option(None, "--budget", "-b", help="Cost budget in USD"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry-run mode"),
    hours: float = typer.Option(4.0, "--hours", "-H", help="Max engagement hours"),
) -> None:
    """Create a new target."""
    if mode not in ("purple_team", "bug_bounty"):
        console.print(f"[red]Invalid mode: {mode}. Use 'purple_team' or 'bug_bounty'.[/red]")
        raise typer.Exit(1)
    try:
        domain_list = parse_scope_string(domains) if domains else []
        ip_list = parse_scope_string(ips) if ips else []
        port_list = [int(p.strip()) for p in ports.split(",") if p.strip()]
    except Exception as e:
        console.print(f"[red]❌ Invalid scope: {e}[/red]")
        raise typer.Exit(1) from e
    mgr = get_target_manager()
    try:
        target = mgr.create(
            slug=slug,
            name=name,
            mode=mode,  # type: ignore[arg-type]
            domains=domain_list,
            ips=ip_list,
            ports=port_list,
            cost_budget_usd=budget,
            dry_run=dry_run,
            max_engagement_hours=hours,
        )
    except Exception as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]✅ Created target: {target.slug}[/green]")
    console.print(f"  Name: {target.name}")
    console.print(f"  Mode: {target.mode}")
    console.print(f"  Domains: {', '.join(target.scope.domains) or '(none)'}")
    console.print(f"  IPs: {', '.join(target.scope.ips) or '(none)'}")
    console.print(f"  Budget: ${target.cost_budget_usd}")


@targets_app.command("list")
def targets_list() -> None:
    """List all targets."""
    reset_target_manager()
    mgr = get_target_manager()
    targets = mgr.list_all()
    if not targets:
        console.print("[dim]No targets yet. Create one with `kryon targets create`.[/dim]")
        return
    from rich.table import Table  # noqa: PLC0415 — lazy import for startup perf

    table = Table(show_header=True, header_style="bold")
    table.add_column("Slug")
    table.add_column("Name")
    table.add_column("Mode")
    table.add_column("State")
    table.add_column("Budget")
    table.add_column("Created")
    for t in targets:
        table.add_row(
            t.slug,
            t.name,
            t.mode,
            t.state,
            f"${t.cost_budget_usd}",
            t.created_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@targets_app.command("show")
def targets_show(slug: str = typer.Argument(...)) -> None:
    """Show full details of a target."""
    reset_target_manager()
    mgr = get_target_manager()
    try:
        t = mgr.get(slug)
    except Exception as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1) from e
    data = t.model_dump(mode="json")
    console.print(
        yaml.safe_dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )


@targets_app.command("authorize")
def targets_authorize(
    slug: str = typer.Argument(...),
    operator: str = typer.Option("cli-operator", "--by", help="Operator identifier"),
    hours: float = typer.Option(4.0, "--hours", "-H", help="Max engagement hours"),
    notes: str = typer.Option("", "--notes", "-n"),
) -> None:
    """Authorize a target. Prints the verbatim prompt, waits for 'authorized'."""
    reset_target_manager()
    mgr = get_target_manager()
    console.print("\n[bold yellow]⚠️  AUTHORIZATION REQUIRED[/bold yellow]\n")
    console.print(
        f"Confirm: (a) the target is [bold]{slug}[/bold], "
        f"(b) you own this application or have written authorization to test it, "
        f"(c) the engagement may run for up to [bold]{hours}[/bold] hours starting now."
    )
    console.print("")
    response = typer.prompt("Reply 'authorized' to proceed (or anything else to abort)")
    if response.strip().lower() != "authorized":
        console.print("[red]❌ Authorization denied[/red]")
        raise typer.Exit(1)
    try:
        mgr.authorize(
            slug=slug,
            authorized_by=operator,
            max_engagement_hours=hours,
            notes=notes,
        )
    except Exception as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]✅ Target authorized: {slug}[/green]")
    console.print(f"  Operator: {operator}")
    console.print(f"  Duration: {hours} hours")


@targets_app.command("delete")
def targets_delete(
    slug: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a target and all its files."""
    reset_target_manager()
    mgr = get_target_manager()
    if not yes:
        confirmed = typer.confirm(
            f"Delete target '{slug}' and ALL its files (audit log, graph, transcripts)?"
        )
        if not confirmed:
            raise typer.Abort()
    if mgr.delete(slug):
        console.print(f"[green]✅ Deleted target: {slug}[/green]")
    else:
        console.print(f"[yellow]Target {slug} did not exist[/yellow]")


if __name__ == "__main__":
    app()
