#!/usr/bin/env python3
import argparse
import json
import re
import heapq
from pathlib import Path
from typing import Dict, List, Set, Tuple


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
    heapq.heapify(ready)
    order = []

    while ready:
        n = heapq.heappop(ready)
        order.append(n)
        for m in outgoing.get(n, set()):
            incoming[m].discard(n)
            if not incoming[m]:
                heapq.heappush(ready, m)

    if len(order) != len(include_keys):
        remaining = [k for k in include_keys if k not in order]
        order.extend(sorted(remaining))

    return order


def compute_levels(nodes: Dict[str, Dict], include_keys: Set[str]) -> Dict[str, int]:
    deps_map = {
        k: set(nodes[k].get("depends_on", {}).get("nodes", [])).intersection(include_keys)
        for k in include_keys
    }
    levels: Dict[str, int] = {}

    def dfs(node_id: str) -> int:
        if node_id in levels:
            return levels[node_id]
        deps = deps_map.get(node_id, set())
        if not deps:
            levels[node_id] = 1
            return 1
        max_dep = max(dfs(d) for d in deps)
        levels[node_id] = max_dep + 1
        return levels[node_id]

    for k in include_keys:
        dfs(k)

    return levels


def resolve_compiled_path(compiled_dir: Path, node: Dict, project_dir: Path) -> Path:
    compiled_path = node.get("compiled_path")
    if compiled_path:
        compiled = Path(compiled_path)
        return compiled if compiled.is_absolute() else project_dir / compiled

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


def strip_catalog_qualifiers(sql: str) -> str:
    # Replace three-part identifiers with two-part (schema.table)
    ident = r"[A-Za-z_][\w$]*"
    sql = re.sub(rf"\b({ident})\.({ident})\.({ident})\b", r"\2.\3", sql)
    sql = re.sub(r'"([^"]+)"\."([^"]+)"\."([^"]+)"', r'"\2"."\3"', sql)
    sql = re.sub(r"`([^`]+)`\.`([^`]+)`\.`([^`]+)`", r"`\2`.`\3`", sql)
    sql = re.sub(r"\[([^\]]+)\]\.\[([^\]]+)\]\.\[([^\]]+)\]", r"[\2].[\3]", sql)
    return sql


def resolve_output_paths(out_path: Path) -> Tuple[Path, str]:
    if out_path.suffix:
        out_dir = out_path.parent
        base_name = out_path.name
    else:
        out_dir = out_path
        base_name = "dbt_compiled.sql"

    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, base_name


def write_sequence_file(
    out_file: Path,
    project_dir: Path,
    env: str | None,
    sequence: int,
    total_sequences: int,
    nodes: Dict[str, Dict],
    compiled_dir: Path,
    project_dir_for_compiled: Path,
    node_ids: List[str],
) -> None:
    with out_file.open("w", encoding="utf-8") as out:
        out.write("-- DBT SQL Compiler\n")
        out.write(f"-- Project: {project_dir}\n")
        if env:
            out.write(f"-- Environment: {env}\n")
        out.write(f"-- Sequence: {sequence:02d} of {total_sequences:02d}\n")
        out.write(f"-- Models: {len(node_ids)}\n\n")

        for unique_id in node_ids:
            node = nodes[unique_id]
            name = node.get("name")
            resource_type = node.get("resource_type")
            compiled_path = resolve_compiled_path(compiled_dir, node, project_dir_for_compiled)

            if not compiled_path.exists():
                out.write(f"-- WARNING: missing compiled file for {unique_id} at {compiled_path}\n\n")
                continue

            sql = read_sql(compiled_path)
            sql = strip_catalog_qualifiers(sql)

            out.write("-- =========================================\n")
            out.write(f"-- {resource_type}: {name}\n")
            out.write(f"-- unique_id: {unique_id}\n")
            out.write("-- =========================================\n\n")
            out.write(sql)
            out.write("\n\n")


def main():
    parser = argparse.ArgumentParser(description="Compile DBT models into ordered SQL files.")
    parser.add_argument("project_dir", help="Path to dbt project")
    parser.add_argument("-o", "--out", required=True, help="Output SQL file or directory")
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

    out_path = Path(args.out).resolve()
    out_dir, base_name = resolve_output_paths(out_path)

    if not include_keys:
        out_file = out_dir / f"01-{base_name}"
        write_sequence_file(
            out_file,
            project_dir,
            args.env,
            1,
            1,
            nodes,
            compiled_dir,
            project_dir,
            [],
        )
        print(f"Wrote {out_file}")
        return

    order = topological_sort(nodes, include_keys)
    levels = compute_levels(nodes, include_keys)
    max_level = max(levels.values(), default=1)

    level_to_nodes: Dict[int, List[str]] = {lvl: [] for lvl in range(1, max_level + 1)}
    for unique_id in order:
        lvl = levels.get(unique_id, 1)
        level_to_nodes.setdefault(lvl, []).append(unique_id)

    for lvl in range(1, max_level + 1):
        file_name = f"{lvl:02d}-{base_name}"
        out_file = out_dir / file_name

        write_sequence_file(
            out_file,
            project_dir,
            args.env,
            lvl,
            max_level,
            nodes,
            compiled_dir,
            project_dir,
            level_to_nodes.get(lvl, []),
        )

        print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
