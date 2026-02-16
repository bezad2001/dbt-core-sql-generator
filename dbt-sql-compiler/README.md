# DBT SQL Compiler

Compiles all DBT models into a single executable SQL file in dependency order.

## Prerequisites

- DBT Core installed and a valid `profiles.yml` configured
- Run `dbt compile` before using this tool (generates `target/manifest.json` and compiled SQL)

## Install

No extra dependencies (Python 3.8+).

## Usage

```bash
python dbt_sql_compiler.py /path/to/dbt/project -o output.sql -e prod
```

### Options

- `-o, --out` Output SQL file path (required)
- `-e, --env` Environment label (optional; for header metadata)
- `--manifest` Optional path to manifest.json (defaults to `target/manifest.json`)
- `--compiled-dir` Optional compiled SQL dir (defaults to `target/compiled`)
- `--include-disabled` Include disabled models
- `--include-seeds` Include seeds
- `--include-snapshots` Include snapshots

## Example

```bash
dbt compile --target prod_databricks
python dbt_sql_compiler.py . -o deployments/databricks_prod.sql -e prod
```

## Notes

- The compiler orders nodes using DBT manifest dependencies.
- It emits a single SQL file with section headers for each model.
