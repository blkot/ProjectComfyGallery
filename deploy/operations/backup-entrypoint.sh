#!/bin/sh
set -eu

if [ "$(id -u)" = "0" ]; then
    install -d -m 0750 -o 10001 -g 10001 "${CG_BACKUP_ROOT:-/backups}"
    exec su-exec 10001:10001 "$0" "$@"
fi

command="${1:-schedule}"
case "$command" in
    schedule)
        interval="${CG_BACKUP_INTERVAL_SECONDS:-86400}"
        while true; do
            /usr/local/bin/comfy-gallery-backup || true
            sleep "$interval"
        done
        ;;
    run)
        exec /usr/local/bin/comfy-gallery-backup
        ;;
    restore)
        shift
        exec /usr/local/bin/comfy-gallery-restore "$@"
        ;;
    *)
        echo "Usage: backup-entrypoint [schedule|run|restore BACKUP_DIRECTORY]" >&2
        exit 2
        ;;
esac
