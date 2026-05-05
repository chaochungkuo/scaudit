from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReferenceManifest:
    id: str
    version: str
    source: str
    species: str
    tissue: str
    condition: str
    technology: str
    path: str
    label_key: str
    gene_id_type: str
    downloaded_at: str | None = None
    checksum: str | None = None


def registry_root(root: Path | None = None) -> Path:
    return root or Path("references")


def registry_path(root: Path | None = None) -> Path:
    return registry_root(root) / "registry.json"


def add_reference(
    source_path: Path,
    reference_id: str,
    species: str,
    tissue: str,
    label_key: str,
    root: Path | None = None,
    condition: str = "",
    technology: str = "",
    version: str = "custom",
    source: str = "local",
    gene_id_type: str = "symbol",
) -> ReferenceManifest:
    if not source_path.exists():
        raise FileNotFoundError(f"reference file not found: {source_path}")
    if not reference_id:
        raise ValueError("reference id is required")
    if not species:
        raise ValueError("species is required")
    if not tissue:
        raise ValueError("tissue is required")
    if not label_key:
        raise ValueError("label key is required")

    root_path = registry_root(root)
    ref_dir = root_path / reference_id
    ref_dir.mkdir(parents=True, exist_ok=True)
    data_path = ref_dir / source_path.name
    shutil.copyfile(source_path, data_path)

    manifest = ReferenceManifest(
        id=reference_id,
        version=version,
        source=source,
        species=species,
        tissue=tissue,
        condition=condition,
        technology=technology,
        path=str(data_path),
        label_key=label_key,
        gene_id_type=gene_id_type,
    )
    manifest_path = ref_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest.__dict__, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    registry = load_registry(root_path)
    registry[reference_id] = {
        "id": reference_id,
        "status": "local",
        "manifest_path": str(manifest_path),
        "data_path": str(data_path),
    }
    save_registry(registry, root_path)
    return manifest


def load_registry(root: Path | None = None) -> dict[str, dict[str, str]]:
    path = registry_path(root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(registry: dict[str, dict[str, str]], root: Path | None = None) -> None:
    root_path = registry_root(root)
    root_path.mkdir(parents=True, exist_ok=True)
    registry_path(root_path).write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def use_reference(config_path: Path, reference_id: str) -> None:
    text = config_path.read_text(encoding="utf-8")
    marker = "selected = []"
    replacement = f'selected = ["{reference_id}"]'
    if marker in text:
        config_path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")
        return
    if "[references]" not in text:
        text += f'\n[references]\nselected = ["{reference_id}"]\n'
        config_path.write_text(text, encoding="utf-8")
        return
    lines = text.splitlines()
    output: list[str] = []
    in_references = False
    replaced = False
    for line in lines:
        if line.strip() == "[references]":
            in_references = True
            output.append(line)
            continue
        if in_references and line.startswith("[") and line.strip() != "[references]":
            if not replaced:
                output.append(replacement)
                replaced = True
            in_references = False
        if in_references and line.strip().startswith("selected"):
            output.append(replacement)
            replaced = True
        else:
            output.append(line)
    if in_references and not replaced:
        output.append(replacement)
    config_path.write_text("\n".join(output) + "\n", encoding="utf-8")
