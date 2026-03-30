#!/bin/sh
set -e
cd "$(dirname "$0")/.."

# Load env from .env.dev so tests use the same credentials as dev compose
set -a
. ./.env.dev
set +a

exec uv run --group test pytest tests/ "$@"
