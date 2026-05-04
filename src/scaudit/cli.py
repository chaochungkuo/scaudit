from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scaudit import __version__
from scaudit.config import build_plan, has_errors, validate_config, write_default_config
from scaudit.rendering import print_bullets, print_status_table


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


def init_config(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: input .h5ad path is required", file=sys.stderr)
        raise SystemExit(2)
    dataset_path = args[0]
    output_path = Path("config.toml")
    config_format = "toml"

    index = 1
    while index < len(args):
        token = args[index]
        if token == "--out" and index + 1 < len(args):
            output_path = Path(args[index + 1])
            index += 2
        elif token == "--format" and index + 1 < len(args):
            config_format = args[index + 1]
            index += 2
        else:
            print(f"Unknown option for init-config: {token}", file=sys.stderr)
            raise SystemExit(2)

    if config_format != "toml":
        print("ERROR: only --format toml is currently supported", file=sys.stderr)
        raise SystemExit(2)

    write_default_config(dataset_path, output_path)
    print(f"Created {output_path}")
    print()
    print("Next:")
    print(f"  scaudit validate {output_path}")
    print(f"  scaudit plan {output_path}")


def validate(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: config path is required", file=sys.stderr)
        raise SystemExit(2)
    config_path = Path(args[0])
    items = validate_config(config_path)
    print_status_table("Config validation", [(item.section, item.status, item.notes) for item in items])
    if has_errors(items):
        raise SystemExit(1)


def plan(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: config path is required", file=sys.stderr)
        raise SystemExit(2)
    config_path = Path(args[0])
    items = validate_config(config_path)
    print_status_table("Config validation", [(item.section, item.status, item.notes) for item in items])
    if has_errors(items):
        raise SystemExit(1)

    run_plan = build_plan(config_path)
    print()
    print(f"Dataset: {run_plan.dataset_path or '(not configured)'}")
    print(f"Output: {run_plan.output_dir}")
    print()
    print_status_table("Methods", [(item.section, item.status, item.notes) for item in run_plan.methods])
    print()
    print_bullets("Outputs", run_plan.outputs)
    print()
    print_bullets("Stages", run_plan.stages)


def _print_help() -> None:
    print("scaudit")
    print()
    print("Usage:")
    print("  scaudit --help")
    print("  scaudit version")
    print("  scaudit doctor")
    print("  scaudit init-config input.h5ad --format toml --out config.toml")
    print("  scaudit validate config.toml")
    print("  scaudit plan config.toml")
    print()
    print("Commands:")
    print("  doctor       Show environment capability checks")
    print("  init-config  Create a starter config.toml")
    print("  plan         Preview the run plan")
    print("  validate     Validate config.toml")
    print("  version      Show scaudit version")


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"--help", "-h", "help"}:
        _print_help()
        return
    command = args[0]
    if command == "doctor":
        doctor()
        return
    if command == "init-config":
        init_config(args[1:])
        return
    if command == "validate":
        validate(args[1:])
        return
    if command == "plan":
        plan(args[1:])
        return
    if command in {"version", "--version", "-V"}:
        version()
        return
    print(f"Unknown command: {command}", file=sys.stderr)
    print("Run 'scaudit --help' for available commands.", file=sys.stderr)
    raise SystemExit(2)
