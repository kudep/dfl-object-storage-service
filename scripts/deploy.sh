#!/bin/sh
set -e
cd "$(dirname "$0")/.."

if [ ! -f .env.deploy ]; then
  echo "Error: .env.deploy not found. Copy .env.deploy.example and fill in real credentials:"
  echo "  cp .env.deploy.example .env.deploy"
  exit 1
fi

exec docker compose --env-file .env.deploy -f compose.yml -f compose.deploy.yml "$@"
