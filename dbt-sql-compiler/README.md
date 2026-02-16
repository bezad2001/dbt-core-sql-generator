# DBT SQL Compiler

Compiles DBT models into **ordered SQL files** based on dependency levels. Models that can run in parallel are grouped into the same sequence number.

## Prerequisites

- DBT Core installed and a valid `profiles.yml` configured
- Run `dbt compile` before using this tool (generates `target/manifest.json` and compiled SQL)

## Install

No extra dependencies (Python 3.8+).

## Usage

```bash
python dbt_sql_compiler.py /path/to/dbt/project -o output.sql -e prod
```

This will produce multiple files:

```
01-output.sql
02-output.sql
...
```

Each file contains models that can run in parallel at that sequence level.

### Options

- `-o, --out` Output SQL file **base name** or directory (required)
- `-e, --env` Environment label (optional; for header metadata)
- `--manifest` Optional path to manifest.json (defaults to `target/manifest.json`)
- `--compiled-dir` Optional compiled SQL dir (defaults to `target/compiled`)
- `--include-disabled` Include disabled models
- `--include-seeds` Include seeds
- `--include-snapshots` Include snapshots

## Catalog-stripping behavior

The compiler removes **catalog qualifiers** from three-part identifiers so the output only contains `schema.table` (two-part) names.

## Example

```bash
dbt compile --target prod_databricks
python dbt_sql_compiler.py . -o deployments/databricks_prod.sql -e prod
```

## Notes

- The compiler orders nodes using DBT manifest dependencies and groups by dependency level.
- Output SQL files are prefixed with `01-`, `02-`, etc.
- Each file contains section headers per model.
