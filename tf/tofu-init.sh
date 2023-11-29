#!/usr/bin/env bash
set -euo pipefail

tofu init \
    -backend-config="bucket=$(cd state-backend; tofu output -raw bucket)" \
    -backend-config="region=$(cd state-backend; tofu output -raw region)" \
    -backend-config="dynamodb_table=$(cd state-backend; tofu output -raw dynamodb_table)" \
    "$@"
