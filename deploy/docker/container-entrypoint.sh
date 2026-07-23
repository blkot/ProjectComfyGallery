#!/bin/sh
set -eu

if [ "$(id -u)" = "0" ]; then
    install -d -o comfy -g comfy /data /data/managed /data/staging
    exec su-exec comfy "$@"
fi

exec "$@"
