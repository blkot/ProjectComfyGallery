#!/bin/sh
set -eu
umask 027

backup_root="$(realpath "${CG_BACKUP_ROOT:-/backups}")"
requested="${1:-}"
target_database="${PGDATABASE:-comfygallery}"
expected_confirmation="restore:$target_database"

if [ -z "$requested" ]; then
    echo "Usage: restore BACKUP_DIRECTORY" >&2
    exit 2
fi
if [ "${CG_RESTORE_CONFIRM:-}" != "$expected_confirmation" ]; then
    echo "Refusing restore. Set CG_RESTORE_CONFIRM=$expected_confirmation" >&2
    exit 2
fi

backup_directory="$(realpath "$requested")"
case "$backup_directory/" in
    "$backup_root/"*) ;;
    *)
        echo "Backup directory must be inside $backup_root" >&2
        exit 2
        ;;
esac

dump="$backup_directory/database.dump"
checksum="$backup_directory/database.dump.sha256"
manifest="$backup_directory/manifest.json"
test -s "$dump"
test -s "$checksum"
test -s "$manifest"

(
    cd "$backup_directory"
    sha256sum -c database.dump.sha256
)
pg_restore --list "$dump" >/dev/null

maintenance_database="${PGMAINTENANCE_DATABASE:-postgres}"
dropdb \
    --host="${PGHOST:-postgres}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-comfygallery}" \
    --maintenance-db="$maintenance_database" \
    --if-exists \
    --force \
    "$target_database"
createdb \
    --host="${PGHOST:-postgres}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-comfygallery}" \
    --maintenance-db="$maintenance_database" \
    "$target_database"
pg_restore \
    --host="${PGHOST:-postgres}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-comfygallery}" \
    --dbname="$target_database" \
    --no-owner \
    --no-acl \
    --exit-on-error \
    "$dump"

echo "Database restore completed into $target_database from $backup_directory"
