#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Set


def load_manifest(manifest_path: Path) -> Dict:
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def topological_sort(nodes: Dict[str, Dict], include_keys: Set[str]) -> List[str]:
    incoming = {k: set() for k in include_keys}
    outgoing = {k: set() for k in include_keys}

    for unique_id in include_keys:
        deps = set(nodes[unique_id].get("depends_on", {}).get("nodes", []))
        deps = deps.intersection(include_keys)
        incoming[unique_id] = deps
        for d in deps:
            outgoing[d].add(unique_id)

    ready = [k for k, v in incoming.items() if not v]
    order = []

    while ready:
        n = ready.pop()
        order.append(n)
        for m in list(outgoing[n]):
            incoming[m].discard(n)
            outgoing[n].discard(m)
            if not incoming[m]:
                ready.append(m)

    if len(order) != len(include_keys):
        remaining = [k for k in include_keys if k not in order]
        order.extend(sorted(remaining))

    return order


def resolve_compiled_path(compiled_dir: Path, node: Dict) -> Path:
    compiled_path = node.get("compiled_path")
    if compiled_path:
        return Path(compiled_path)

    original_file_path = node.get("original_file_path")
    if not original_file_path:
        raise FileNotFoundError("No compiled_path or original_file_path for node")
    return compiled_dir / original_file_path


def read_sql(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read().strip()


def should_include(node: Dict, include_disabled: bool, resource_types: Set[str]) -> bool:
    if not include_disabled and node.get("config", {}).get("enabled") is False:
        return False
    return node.get("resource_type") in resource_types


def main():
    parser = argparse.ArgumentParser(description="Compile DBT models into a single SQL file.")
    parser.add_argument("project_dir", help="Path to dbt project")
    parser.add_argument("-o", "--out", required=True, help="Output SQL file")
    parser.add_argument("-e", "--env", default=None, help="Environment label")
    parser.add_argument("--manifest", default=None, help="Path to manifest.json")
    parser.add_argument("--compiled-dir", default=None, help="Path to compiled SQL directory")
    parser.add_argument("--include-disabled", action="store_true")
    parser.add_argument("--include-seeds", action="store_true")
    parser.add_argument("--include-snapshots", action="store_true")

    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    manifest_path = Path(args.manifest) if args.manifest else project_dir / "target" / "manifest.json"
    compiled_dir = Path(args.compiled_dir) if args.compiled_dir else project_dir / "target" / "compiled"

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found at {manifest_path}. Run `dbt compile` first.")

    manifest = load_manifest(manifest_path)
    nodes = manifest.get("nodes", {})

    resource_types = {"model"}
    if args.include_seeds:
        resource_types.add("seed")
    if args.include_snapshots:
        resource_types.add("snapshot")

    include_keys = {
        k for k, v in nodes.items()
        if should_include(v, args.include_disabled, resource_types)
    }

    order = topological_sort(nodes, include_keys)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as out:
        out.write("-- DBT SQL Compiler\n")
        out.write(f"-- Project: {project_dir}\n")
        if args.env:
            out.write(f"-- Environment: {args.env}\n")
        out.write(f"-- Models: {len(order)}\n\n")

        for unique_id in order:
            node = nodes[unique_id]
            name = node.get("name")
            resource_type = node.get("resource_type")
            compiled_path = resolve_compiled_path(compiled_dir, node)

            if not compiled_path.exists():
                out.write(f"-- WARNING: missing compiled file for {unique_id} at {compiled_path}\n\n")
                continue

            sql = read_sql(compiled_path)

            out.write("-- =========================================\n")
            out.write(f"-- {resource_type}: {name}\n")
            out.write(f"-- unique_id: {unique_id}\n")
            out.write("-- =========================================\n\n")
            out.write(sql)
            out.write("\n\n")

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
