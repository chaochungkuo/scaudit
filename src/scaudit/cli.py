from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass
from typing import Sequence

from scaudit import __version__


@dataclass(frozen=True)
class Capability:
    component: str
    status: str
    details: str


def _module_status(module_name: str, label: str | None = None, optional: bool = False) -> Capability:
    found = importlib.util.find_spec(module_name) is not None
    component = label or module_name
    if found:
        return Capability(component, "OK", "installed")
    if optional:
        return Capability(component, "SKIPPED", "optional dependency not installed")
    return Capability(component, "WARN", "not installed")


def collect_capabilities() -> list[Capability]:
    return [
        Capability("Python", "OK", platform.python_version()),
        _module_status("rich"),
        _module_status("typer"),
        _module_status("anndata", optional=True),
        _module_status("scanpy", optional=True),
        _module_status("celltypist", optional=True),
        _module_status("scvi", label="scvi-tools", optional=True),
        _module_status("plotly", optional=True),
    ]


def _print_plain_table(rows: Sequence[Capability]) -> None:
    headers = ("Component", "Status", "Details")
    widths = [
        max(len(headers[0]), *(len(row.component) for row in rows)),
        max(len(headers[1]), *(len(row.status) for row in rows)),
        max(len(headers[2]), *(len(row.details) for row in rows)),
    ]
    line = f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  {headers[2]:<{widths[2]}}"
    print(line)
    print("-" * len(line))
    for row in rows:
        print(f"{row.component:<{widths[0]}}  {row.status:<{widths[1]}}  {row.details:<{widths[2]}}")


def doctor() -> None:
    capabilities = collect_capabilities()
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
    except ModuleNotFoundError:
        print("scaudit doctor")
        print()
        _print_plain_table(capabilities)
        print()
        print("Next:")
        print("  scaudit init-config input.h5ad --format toml --out config.toml")
        return

    console = Console()
    table = Table(title="Environment", show_lines=False)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    status_style = {
        "OK": "green",
        "WARN": "yellow",
        "SKIPPED": "dim",
        "ERROR": "red",
    }
    for row in capabilities:
        table.add_row(row.component, f"[{status_style.get(row.status, 'white')}]{row.status}[/]", row.details)

    console.print(Panel.fit("[bold navy_blue]scaudit doctor[/]", border_style="cyan"))
    console.print(table)
    console.print()
    console.print("[bold]Next:[/]")
    console.print("  [cyan]scaudit init-config input.h5ad --format toml --out config.toml[/]")


def version() -> None:
    print(f"scaudit {__version__}")


def _print_help() -> None:
    print("scaudit")
    print()
    print("Usage:")
    print("  scaudit --help")
    print("  scaudit version")
    print("  scaudit doctor")
    print()
    print("Commands:")
    print("  doctor   Show environment capability checks")
    print("  version  Show scaudit version")


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"--help", "-h", "help"}:
        _print_help()
        return
    command = args[0]
    if command == "doctor":
        doctor()
        return
    if command in {"version", "--version", "-V"}:
        version()
        return
    print(f"Unknown command: {command}", file=sys.stderr)
    print("Run 'scaudit --help' for available commands.", file=sys.stderr)
    raise SystemExit(2)
