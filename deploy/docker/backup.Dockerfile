FROM postgres:17-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193

ARG CG_PROJECT_VERSION=0.1.0-rc.3

LABEL org.opencontainers.image.title="Project Comfy Gallery backup" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION"

RUN apk upgrade --no-cache && \
    apk add --no-cache su-exec && \
    rm /usr/local/bin/gosu

COPY deploy/operations/backup-entrypoint.sh /usr/local/bin/backup-entrypoint
COPY deploy/operations/backup.sh /usr/local/bin/comfy-gallery-backup
COPY deploy/operations/restore.sh /usr/local/bin/comfy-gallery-restore

RUN chmod 0555 \
    /usr/local/bin/backup-entrypoint \
    /usr/local/bin/comfy-gallery-backup \
    /usr/local/bin/comfy-gallery-restore

ENTRYPOINT ["/usr/local/bin/backup-entrypoint"]
CMD ["schedule"]
