from __future__ import annotations

from collections.abc import Iterable


def print_status_table(title: str, rows: Iterable[tuple[str, str, str]]) -> None:
    materialized = list(rows)
    try:
        from rich.console import Console
        from rich.table import Table
    except ModuleNotFoundError:
        print(title)
        print()
        _print_plain_table(materialized)
        return

    status_style = {
        "OK": "green",
        "WARN": "yellow",
        "ERROR": "red",
        "SKIPPED": "dim",
    }
    table = Table(title=title, show_lines=False)
    table.add_column("Section", style="bold")
    table.add_column("Status")
    table.add_column("Notes")
    for section, status, notes in materialized:
        table.add_row(section, f"[{status_style.get(status, 'white')}]{status}[/]", notes)
    Console().print(table)


def print_bullets(title: str, values: Iterable[str]) -> None:
    print(title)
    for value in values:
        print(f"  - {value}")


def _print_plain_table(rows: list[tuple[str, str, str]]) -> None:
    headers = ("Section", "Status", "Notes")
    widths = [
        max(len(headers[0]), *(len(row[0]) for row in rows), 1),
        max(len(headers[1]), *(len(row[1]) for row in rows), 1),
        max(len(headers[2]), *(len(row[2]) for row in rows), 1),
    ]
    line = f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  {headers[2]:<{widths[2]}}"
    print(line)
    print("-" * len(line))
    for section, status, notes in rows:
        print(f"{section:<{widths[0]}}  {status:<{widths[1]}}  {notes:<{widths[2]}}")
