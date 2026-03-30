#!/bin/sh
set -e
cd "$(dirname "$0")/.."
exec docker compose --env-file .env.dev -f compose.yml -f compose.dev.yml "$@"
