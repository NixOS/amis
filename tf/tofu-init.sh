#!/usr/bin/env bash
set -euo pipefail

(cd bootstrap; tofu init)

tofu init \
    -backend-config="bucket=$(cd bootstrap; tofu output -raw bucket)" \
    -backend-config="region=$(cd bootstrap; tofu output -raw region)" \
    -backend-config="dynamodb_table=$(cd bootstrap; tofu output -raw dynamodb_table)" \
    "$@"
