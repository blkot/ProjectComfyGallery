#!/bin/sh
set -eu
umask 027

backup_root="${CG_BACKUP_ROOT:-/backups}"
daily_keep="${CG_BACKUP_DAILY_KEEP:-7}"
weekly_keep="${CG_BACKUP_WEEKLY_KEEP:-4}"
backup_id="cg-$(date -u +%Y%m%dT%H%M%SZ)"
attempted_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
daily_root="$backup_root/daily"
weekly_root="$backup_root/weekly"
temporary="$backup_root/.tmp-$backup_id"
status_temporary="$backup_root/.backup-status.json.tmp"
completed=0

write_failure_status() {
    cat >"$status_temporary" <<EOF
{"status":"error","attempted_at":"$attempted_at","error":"database backup command failed"}
EOF
    mv "$status_temporary" "$backup_root/.backup-status.json"
}

cleanup() {
    result=$?
    if [ "$completed" -ne 1 ]; then
        rm -rf "$temporary"
        write_failure_status
    fi
    exit "$result"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$daily_root" "$weekly_root" "$temporary"

pg_dump \
    --host="${PGHOST:-postgres}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-comfygallery}" \
    --dbname="${PGDATABASE:-comfygallery}" \
    --format=custom \
    --compress=6 \
    --no-owner \
    --no-acl \
    --file="$temporary/database.dump"

test -s "$temporary/database.dump"
pg_restore --list "$temporary/database.dump" >/dev/null

(
    cd "$temporary"
    sha256sum database.dump >database.dump.sha256
)

schema_version="$(
    psql \
        --host="${PGHOST:-postgres}" \
        --port="${PGPORT:-5432}" \
        --username="${PGUSER:-comfygallery}" \
        --dbname="${PGDATABASE:-comfygallery}" \
        --tuples-only \
        --no-align \
        --command='SELECT version_num FROM alembic_version LIMIT 1' |
        tr -cd 'A-Za-z0-9_.-'
)"
dump_sha256="$(cut -d' ' -f1 "$temporary/database.dump.sha256")"
byte_size="$(stat -c '%s' "$temporary/database.dump")"
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat >"$temporary/manifest.json" <<EOF
{
  "backup_schema_version": "1",
  "backup_id": "$backup_id",
  "completed_at": "$completed_at",
  "database": "${PGDATABASE:-comfygallery}",
  "alembic_version": "$schema_version",
  "dump_format": "PostgreSQL custom",
  "dump_sha256": "$dump_sha256",
  "byte_size": $byte_size
}
EOF

mv "$temporary" "$daily_root/$backup_id"

if [ "$(date -u +%u)" = "7" ]; then
    cp -a "$daily_root/$backup_id" "$weekly_root/$backup_id"
fi

prune_directory() {
    directory="$1"
    keep="$2"
    index=0
    for entry_name in $(ls -1 "$directory" | sort -r); do
        case "$entry_name" in
            cg-*) ;;
            *) continue ;;
        esac
        index=$((index + 1))
        if [ "$index" -gt "$keep" ]; then
            rm -rf "$directory/$entry_name"
        fi
    done
}

prune_directory "$daily_root" "$daily_keep"
prune_directory "$weekly_root" "$weekly_keep"

cat >"$status_temporary" <<EOF
{"status":"ok","backup_id":"$backup_id","completed_at":"$completed_at","byte_size":$byte_size,"sha256":"$dump_sha256","alembic_version":"$schema_version"}
EOF
mv "$status_temporary" "$backup_root/.backup-status.json"
completed=1
trap - EXIT HUP INT TERM

echo "Database backup completed: $backup_id ($byte_size bytes)"
