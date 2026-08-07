#!/usr/bin/env bash
set -euo pipefail

backup_root=${1:?Usage: backup-postgres.sh BACKUP_ROOT [PROJECT_PATH]}
project_path=${2:-$(cd "$(dirname "$0")/.." && pwd)}
: "${DJANGO_DB_NAME:?DJANGO_DB_NAME is required}"
: "${DJANGO_DB_USER:?DJANGO_DB_USER is required}"
: "${DJANGO_DB_PASSWORD:?DJANGO_DB_PASSWORD is required}"
: "${DJANGO_DB_HOST:?DJANGO_DB_HOST is required}"
: "${DJANGO_DB_PORT:?DJANGO_DB_PORT is required}"

timestamp=$(date +%Y%m%d-%H%M%S)
destination="$backup_root/$timestamp"
mkdir -p "$destination"
export PGPASSWORD="$DJANGO_DB_PASSWORD"

pg_dump --format=custom --file="$destination/database.dump" --host="$DJANGO_DB_HOST" --port="$DJANGO_DB_PORT" --username="$DJANGO_DB_USER" "$DJANGO_DB_NAME"
if [[ -d "$project_path/media" ]]; then
    tar -C "$project_path" -czf "$destination/media.tar.gz" media
fi
sha256sum "$destination"/* > "$destination/checksums.sha256"
printf 'Backup completed: %s\n' "$destination"
