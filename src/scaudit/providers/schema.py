from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def package_versions(packages: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version()}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    return versions


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative_to(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def render_qmd(qmd_path: Path) -> tuple[Path | None, str]:
    qmd_path = qmd_path.resolve()
    quarto = shutil.which("quarto")
    if not quarto:
        return None, "Quarto was not available; wrote a fallback HTML provider report."
    source_dir = str(Path(__file__).resolve().parents[2])
    env = dict(os.environ)
    env["PYTHONPATH"] = source_dir + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("QUARTO_PYTHON", sys.executable)
    try:
        completed = subprocess.run(
            [quarto, "render", str(qmd_path), "--to", "html"],
            cwd=qmd_path.parent,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "Quarto render failed.").strip().splitlines()
        detail = message[-1] if message else "Quarto render failed."
        return None, f"Quarto render failed; wrote a fallback HTML provider report. Detail: {detail}"
    except Exception as exc:
        return None, f"Quarto render failed; wrote a fallback HTML provider report. Detail: {exc}"
    html_path = qmd_path.with_suffix(".html")
    if html_path.exists():
        return html_path, ""
    detail = (completed.stderr or completed.stdout or "Quarto did not write HTML.").strip().splitlines()
    return None, detail[-1] if detail else "Quarto did not write HTML."
