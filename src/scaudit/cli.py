from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scaudit import __version__
from scaudit.config import build_plan, has_errors, validate_config, write_default_config
from scaudit.data import diagnose_dataset
from scaudit.references import add_reference, load_registry, use_reference
from scaudit.rendering import print_bullets, print_status_table
from scaudit.review import import_review_table
from scaudit.run import finalize_run, prepare_run


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


def diagnose(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: input .h5ad path is required", file=sys.stderr)
        raise SystemExit(2)
    dataset_path = Path(args[0])
    output_dir = Path("results")
    cluster_key = ""

    index = 1
    while index < len(args):
        token = args[index]
        if token == "--out" and index + 1 < len(args):
            output_dir = Path(args[index + 1])
            index += 2
        elif token == "--cluster-key" and index + 1 < len(args):
            cluster_key = args[index + 1]
            index += 2
        else:
            print(f"Unknown option for diagnose: {token}", file=sys.stderr)
            raise SystemExit(2)

    diagnosis = diagnose_dataset(dataset_path, cluster_key=cluster_key)
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnosis_path = output_dir / "diagnosis.json"
    import json

    diagnosis_path.write_text(json.dumps(diagnosis.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print_status_table(
        "Dataset diagnosis",
        [
            ("path", "OK" if diagnosis.file_exists else "ERROR", diagnosis.path),
            ("readable", "OK" if diagnosis.readable else "WARN", str(diagnosis.readable)),
            ("cells", "OK" if diagnosis.n_obs is not None else "SKIPPED", str(diagnosis.n_obs)),
            ("genes", "OK" if diagnosis.n_vars is not None else "SKIPPED", str(diagnosis.n_vars)),
            ("cluster_key", "OK" if diagnosis.cluster_count is not None else "WARN", diagnosis.cluster_key or "(not set)"),
        ],
    )
    if diagnosis.warnings:
        print()
        print_bullets("Warnings", diagnosis.warnings)
    print()
    print(f"Wrote {diagnosis_path}")


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


def run(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: config path is required", file=sys.stderr)
        raise SystemExit(2)
    config_path = Path(args[0])
    items = validate_config(config_path)
    print_status_table("Config validation", [(item.section, item.status, item.notes) for item in items])
    if has_errors(items):
        raise SystemExit(1)

    print()
    print("Running scaudit annotation audit")
    print("[1/4] Validating config      OK")
    print("[2/4] Preparing outputs      RUNNING")
    outputs = prepare_run(config_path)
    print("[2/4] Preparing outputs      OK")
    print("[3/4] Writing placeholders   OK")
    print("[4/4] Final summary          OK")
    print()
    print("Draft annotation audit skeleton complete")
    print()
    print("Outputs:")
    print(f"  Report: {outputs.report_index}")
    print(f"  Annotation cards: {outputs.annotation_cards}")
    print(f"  Review table: {outputs.review_table}")
    print(f"  Reproducibility: {outputs.reproducibility}")
    print()
    print("Next:")
    print(f"  Open {outputs.report_index}")
    print("  Implement marker evidence in the next milestone")


def finalize(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: run directory is required", file=sys.stderr)
        raise SystemExit(2)
    run_dir = Path(args[0])
    output_dir = Path("final")

    index = 1
    while index < len(args):
        token = args[index]
        if token == "--out" and index + 1 < len(args):
            output_dir = Path(args[index + 1])
            index += 2
        else:
            print(f"Unknown option for finalize: {token}", file=sys.stderr)
            raise SystemExit(2)

    try:
        outputs = finalize_run(run_dir, output_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("Final annotation audit skeleton complete")
    print()
    print("Outputs:")
    print(f"  Report: {outputs.report_index}")
    print(f"  Final annotation cards: {outputs.annotation_cards}")
    print(f"  Final summary: {outputs.annotation_summary}")
    print(f"  Review audit: {outputs.review_audit}")


def review(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: review subcommand is required", file=sys.stderr)
        raise SystemExit(2)
    subcommand = args[0]
    if subcommand != "import":
        print(f"Unknown review subcommand: {subcommand}", file=sys.stderr)
        raise SystemExit(2)
    if len(args) < 2:
        print("ERROR: review table path is required", file=sys.stderr)
        raise SystemExit(2)

    source = Path(args[1])
    run_dir = Path("results")
    index = 2
    while index < len(args):
        token = args[index]
        if token == "--run" and index + 1 < len(args):
            run_dir = Path(args[index + 1])
            index += 2
        else:
            print(f"Unknown option for review import: {token}", file=sys.stderr)
            raise SystemExit(2)

    try:
        result = import_review_table(source, run_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("Review table imported")
    print()
    print(f"Rows: {result.row_count}")
    print(f"Reviewed table: {result.reviewed_table}")
    print(f"Review audit: {result.audit_path}")
    if result.warnings:
        print()
        print_bullets("Warnings", result.warnings)
    print()
    print("Next:")
    print(f"  scaudit finalize {result.run_dir} --out final/")


def reference(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: reference subcommand is required", file=sys.stderr)
        raise SystemExit(2)
    subcommand = args[0]
    if subcommand == "list":
        registry = load_registry()
        if not registry:
            print("No references registered.")
            return
        print_status_table(
            "References",
            [(item["id"], item.get("status", "unknown"), item.get("data_path", "")) for item in registry.values()],
        )
        return
    if subcommand == "use":
        if len(args) < 2:
            print("ERROR: reference id is required", file=sys.stderr)
            raise SystemExit(2)
        reference_id = args[1]
        config_path = Path("config.toml")
        index = 2
        while index < len(args):
            token = args[index]
            if token == "--config" and index + 1 < len(args):
                config_path = Path(args[index + 1])
                index += 2
            else:
                print(f"Unknown option for reference use: {token}", file=sys.stderr)
                raise SystemExit(2)
        use_reference(config_path, reference_id)
        print(f"Updated {config_path}: selected {reference_id}")
        return
    if subcommand == "add":
        _reference_add(args[1:])
        return
    print(f"Unknown reference subcommand: {subcommand}", file=sys.stderr)
    raise SystemExit(2)


def _reference_add(args: Sequence[str]) -> None:
    if not args:
        print("ERROR: reference file path is required", file=sys.stderr)
        raise SystemExit(2)
    source_path = Path(args[0])
    options = {
        "id": "",
        "species": "",
        "tissue": "",
        "condition": "",
        "technology": "",
        "label_key": "",
        "version": "custom",
        "source": "local",
        "gene_id_type": "symbol",
    }
    index = 1
    while index < len(args):
        token = args[index]
        value_keys = {
            "--id": "id",
            "--species": "species",
            "--tissue": "tissue",
            "--condition": "condition",
            "--technology": "technology",
            "--label-key": "label_key",
            "--version": "version",
            "--source": "source",
            "--gene-id-type": "gene_id_type",
        }
        if token in value_keys and index + 1 < len(args):
            options[value_keys[token]] = args[index + 1]
            index += 2
        else:
            print(f"Unknown option for reference add: {token}", file=sys.stderr)
            raise SystemExit(2)
    try:
        manifest = add_reference(
            source_path,
            reference_id=options["id"],
            species=options["species"],
            tissue=options["tissue"],
            condition=options["condition"],
            technology=options["technology"],
            label_key=options["label_key"],
            version=options["version"],
            source=options["source"],
            gene_id_type=options["gene_id_type"],
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Registered reference: {manifest.id}")
    print(f"Path: {manifest.path}")


def _print_help() -> None:
    print("scaudit")
    print()
    print("Usage:")
    print("  scaudit --help")
    print("  scaudit version")
    print("  scaudit doctor")
    print("  scaudit diagnose input.h5ad --cluster-key leiden --out results/")
    print("  scaudit init-config input.h5ad --format toml --out config.toml")
    print("  scaudit validate config.toml")
    print("  scaudit plan config.toml")
    print("  scaudit run config.toml")
    print("  scaudit review import results/review_table.csv --run results/")
    print("  scaudit reference add my_ref.h5ad --id my_ref --species mouse --tissue heart --label-key cell_type")
    print("  scaudit reference list")
    print("  scaudit reference use my_ref --config config.toml")
    print("  scaudit finalize results/ --out final/")
    print()
    print("Commands:")
    print("  diagnose    Inspect dataset structure and metadata")
    print("  doctor       Show environment capability checks")
    print("  finalize     Freeze a draft run into final output skeleton")
    print("  init-config  Create a starter config.toml")
    print("  plan         Preview the run plan")
    print("  reference    Manage local reference registry")
    print("  review       Import human review tables")
    print("  run          Create draft audit output skeleton")
    print("  validate     Validate config.toml")
    print("  version      Show scaudit version")


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"--help", "-h", "help"}:
        _print_help()
        return
    command = args[0]
    if command == "diagnose":
        diagnose(args[1:])
        return
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
    if command == "run":
        run(args[1:])
        return
    if command == "finalize":
        finalize(args[1:])
        return
    if command == "review":
        review(args[1:])
        return
    if command == "reference":
        reference(args[1:])
        return
    if command in {"version", "--version", "-V"}:
        version()
        return
    print(f"Unknown command: {command}", file=sys.stderr)
    print("Run 'scaudit --help' for available commands.", file=sys.stderr)
    raise SystemExit(2)
