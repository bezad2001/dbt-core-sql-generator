#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=${1:-}
ENVIRONMENT=${2:-}
WAREHOUSE=${3:-}

if [[ -z "$PROJECT_DIR" || -z "$ENVIRONMENT" || -z "$WAREHOUSE" ]]; then
  echo "Usage: deploy_dbt.sh <project_dir> <environment> <warehouse>"
  exit 1
fi

TARGET="${ENVIRONMENT}_${WAREHOUSE}"

echo "Deploying to $TARGET..."

cd "$PROJECT_DIR"

dbt compile --target "$TARGET"

python "$PWD/../dbt_sql_compiler.py" . \
  -o "deployments/${WAREHOUSE}_${ENVIRONMENT}.sql" \
  -e "$ENVIRONMENT"

if [[ "$WAREHOUSE" == "databricks" ]]; then
  echo "Upload to Databricks manually or via API."
elif [[ "$WAREHOUSE" == "emr" ]]; then
  echo "Upload to S3 and submit to EMR manually or via script."
else
  echo "Unknown warehouse: $WAREHOUSE"
  exit 2
fi

echo "Deployment complete!"
